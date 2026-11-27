"""
AI Engine: project brain.

Uses a local specialized Ollama model (resume-optimizer) built from Qwen.
Falls back to PEFT/transformers only when a CUDA LoRA adapter is present.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
	text = _THINK_PATTERN.sub("", text)
	return text.strip()


SYSTEM_RULES = """You are an expert AI Resume Optimizer.
THE CANDIDATE'S EXISTING RESUME IS THE SOLE SOURCE OF TRUTH.
Return ONLY the complete resume. No commentary.

Section order. Omit a section only when the original resume has nothing for it:
PROFESSIONAL SUMMARY
TECHNICAL SKILLS
PROFESSIONAL EXPERIENCE
INTERNSHIP EXPERIENCE
PROJECTS
EDUCATION
CERTIFICATIONS
ACHIEVEMENTS

Line 1 is the name. Line 2 is only the contact line:
phone | email | linkedin | github | leetcode | portfolio
Never put the summary on the contact line.

PROFESSIONAL SUMMARY
Write 2 to 3 sentences for this job.
Lead with the candidate's real background and the job skills they already have.
Name one or two real projects that use those skills.
Do not write "targeting the <role> role at <company>".
Do not write "matches the skills this role emphasizes".
Do not invent skills.

TECHNICAL SKILLS
Use only these labels, and only lines the resume actually supports:
Languages:
Core CS:
Frontend:
Backend:
Databases:
AI/ML & GenAI:
Tools & Cloud:
Keep hyphenated names whole: Object-Oriented Programming, Scikit-learn, full-stack.
Do not add an Other line.
Do not put project sentences or phrases like "Engineered a full" or "Including crop recommendation" in skills.
Do not add a skill just because the job description mentions it.

Keep real employers, titles, dates, projects, education, certifications, and metrics.
Do not invent any of those.
Do not append "leveraging <keywords>" to bullets.
Do not add a SOFT SKILLS section unless the original resume already has one.
Do not print a title line that says resume."""

PRODUCTION_SYSTEM_PROMPT = SYSTEM_RULES


class ModelManager:
	"""Project LLM brain. Fine-tuned Ollama resume-optimizer, with optional PEFT adapter."""

	def __init__(self):
		self.model = None
		self.tokenizer = None
		self.is_loaded = False
		self.load_error = None
		self.backend = None
		self.model_name = settings.OLLAMA_MODEL
		self.adapter_path = settings.ADAPTER_PATH
		self.adapter_loaded = False
		self.ollama_host = settings.OLLAMA_HOST.rstrip("/")

	def load(self) -> None:
		if self.is_loaded:
			return

		adapter = (settings.ADAPTER_PATH or "").strip()
		base = (settings.BASE_MODEL or settings.MODEL_NAME or "").strip()

		if adapter and os.path.isdir(adapter) and os.path.exists(os.path.join(adapter, "adapter_config.json")):
			try:
				self._load_peft(base, adapter)
				return
			except Exception as exc:
				logger.warning("PEFT load failed, trying Ollama: %s", exc)
				self.load_error = str(exc)

		try:
			self._load_ollama()
			return
		except Exception as exc:
			self.is_loaded = False
			self.load_error = str(exc)
			logger.error(
				"Fine-tuned LLM is not loaded. Start Ollama and run: ollama create resume-optimizer -f backend/Modelfile. %s",
				exc,
			)

	def _ollama_json(self, path: str, payload: Optional[dict] = None, timeout: int = 30) -> dict:
		url = f"{self.ollama_host}{path}"
		data = None if payload is None else json.dumps(payload).encode("utf-8")
		req = urllib.request.Request(
			url,
			data=data,
			headers={"Content-Type": "application/json"},
			method="GET" if payload is None else "POST",
		)
		with urllib.request.urlopen(req, timeout=timeout) as resp:
			raw = resp.read().decode("utf-8")
		return json.loads(raw) if raw else {}

	def _ollama_tags(self) -> list[str]:
		try:
			body = self._ollama_json("/api/tags")
			return [m.get("name", "") for m in body.get("models", [])]
		except Exception as exc:
			raise RuntimeError(
				f"Ollama is not reachable at {self.ollama_host}. "
				"Start Ollama, then retry."
			) from exc

	def _pick_ollama_model(self, installed: list[str]) -> str:
		preferred = [
			settings.OLLAMA_MODEL,
			"resume-optimizer:latest",
			"resume-optimizer",
		]
		installed_set = set(installed)
		for name in preferred:
			if not name:
				continue
			if name in installed_set:
				return name
			if f"{name}:latest" in installed_set:
				return f"{name}:latest"
		raise RuntimeError(
			"Fine-tuned model 'resume-optimizer' is not installed. "
			"Run: ollama create resume-optimizer -f backend/Modelfile"
		)

	def _load_ollama(self) -> None:
		installed = self._ollama_tags()
		self.model_name = self._pick_ollama_model(installed)
		# Warm-up with a tiny generate so the first user request is not cold.
		payload = {
			"model": self.model_name,
			"messages": [
				{"role": "user", "content": "Reply with OK."},
			],
			"stream": False,
			"keep_alive": "30m",
			"options": {"temperature": 0, "num_predict": 4, "num_ctx": 2048},
		}
		self._ollama_json("/api/chat", payload, timeout=max(settings.MODEL_TIMEOUT, 180))
		self.backend = "ollama"
		self.is_loaded = True
		self.load_error = None
		self.adapter_loaded = self.model_name.startswith("resume-optimizer")
		logger.info("Ollama model ready: %s", self.model_name)

	def _load_peft(self, model_name: str, adapter_path: str) -> None:
		import torch
		from peft import PeftModel
		from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

		if not model_name:
			model_name = "Qwen/Qwen2.5-1.5B-Instruct"

		load_kwargs = {
			"trust_remote_code": True,
			"device_map": "auto",
		}
		if torch.cuda.is_available() and settings.LOAD_IN_4BIT:
			load_kwargs["quantization_config"] = BitsAndBytesConfig(
				load_in_4bit=True,
				bnb_4bit_quant_type="nf4",
				bnb_4bit_use_double_quant=True,
				bnb_4bit_compute_dtype=torch.float16,
			)
			load_kwargs["torch_dtype"] = torch.float16
		else:
			load_kwargs["torch_dtype"] = torch.float32

		self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
		if self.tokenizer.pad_token is None:
			self.tokenizer.pad_token = self.tokenizer.eos_token

		self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
		self.model = PeftModel.from_pretrained(self.model, adapter_path)
		self.model.eval()
		self.backend = "peft"
		self.model_name = model_name
		self.adapter_path = adapter_path
		self.adapter_loaded = True
		self.is_loaded = True
		self.load_error = None

	def generate_sync(
		self,
		prompt: Optional[str] = None,
		messages: Optional[list] = None,
		max_new_tokens: int = 1024,
		temperature: float = 0.2,
	) -> str:
		if not self.is_loaded:
			self.load()
		if not self.is_loaded:
			return ""

		if messages is None:
			if not prompt:
				return ""
			messages = [
				{"role": "system", "content": SYSTEM_RULES},
				{"role": "user", "content": prompt},
			]
		else:
			messages = [dict(m) for m in messages]
			if not any(m.get("role") == "system" for m in messages):
				messages = [{"role": "system", "content": SYSTEM_RULES}] + messages

		if self.backend == "ollama":
			# Modelfile already has SYSTEM. A second copy doubles CPU prefill and causes timeouts.
			messages = [m for m in messages if m.get("role") != "system"]
			return self._generate_ollama(messages, max_new_tokens, temperature)
		return self._generate_peft(messages, max_new_tokens, temperature)

	async def generate(
		self,
		prompt: Optional[str] = None,
		messages: Optional[list] = None,
		max_new_tokens: int = 1024,
		temperature: float = 0.2,
	) -> str:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor(
			None,
			lambda: self.generate_sync(
				prompt=prompt,
				messages=messages,
				max_new_tokens=max_new_tokens,
				temperature=temperature,
			),
		)

	def _generate_ollama(self, messages: list, max_new_tokens: int, temperature: float) -> str:
		# Stream so the socket stays alive on CPU. 900 tokens is enough for one page.
		predict = max(64, min(int(max_new_tokens or 512), 512))
		payload = {
			"model": self.model_name,
			"messages": messages,
			"stream": True,
			"keep_alive": "30m",
			"options": {
				"temperature": temperature,
				"num_predict": predict,
				"num_ctx": 2048,
			},
		}
		chunks: list[str] = []
		timeout = max(int(settings.MODEL_TIMEOUT or 600), 600)
		try:
			url = f"{self.ollama_host}/api/chat"
			req = urllib.request.Request(
				url,
				data=json.dumps(payload).encode("utf-8"),
				headers={"Content-Type": "application/json"},
				method="POST",
			)
			with urllib.request.urlopen(req, timeout=timeout) as resp:
				for raw_line in resp:
					line = raw_line.decode("utf-8", errors="ignore").strip()
					if not line:
						continue
					try:
						obj = json.loads(line)
					except json.JSONDecodeError:
						continue
					piece = (obj.get("message") or {}).get("content") or obj.get("response") or ""
					if piece:
						chunks.append(piece)
					if obj.get("done"):
						break
			return _strip_think("".join(chunks))
		except urllib.error.HTTPError as exc:
			detail = exc.read().decode("utf-8", errors="ignore")
			logger.error("Ollama HTTP error: %s %s", exc.code, detail)
			return _strip_think("".join(chunks))
		except Exception as exc:
			text = _strip_think("".join(chunks))
			if len(text) >= 50:
				logger.warning("Ollama generation interrupted after %s chars: %s", len(text), exc)
				return text
			logger.error("Ollama generation failed: %s", exc)
			return ""

	def _generate_peft(self, messages: list, max_new_tokens: int, temperature: float) -> str:
		import torch

		try:
			try:
				prompt = self.tokenizer.apply_chat_template(
					messages,
					tokenize=False,
					add_generation_prompt=True,
					enable_thinking=False,
				)
			except TypeError:
				prompt = self.tokenizer.apply_chat_template(
					messages,
					tokenize=False,
					add_generation_prompt=True,
				)
			inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
			device = next(self.model.parameters()).device
			inputs = {k: v.to(device) for k, v in inputs.items()}
			with torch.no_grad():
				out = self.model.generate(
					**inputs,
					max_new_tokens=max_new_tokens,
					do_sample=temperature > 0,
					temperature=max(temperature, 1e-5),
					pad_token_id=self.tokenizer.eos_token_id,
					eos_token_id=self.tokenizer.eos_token_id,
					repetition_penalty=1.05,
				)
			gen = out[0][inputs["input_ids"].shape[1]:]
			return _strip_think(self.tokenizer.decode(gen, skip_special_tokens=True))
		except Exception as exc:
			logger.error("PEFT generation failed: %s", exc)
			return ""

	def unload(self) -> None:
		self.model = None
		self.tokenizer = None
		self.is_loaded = False

	def get_status(self) -> dict:
		return {
			"model_loaded": self.is_loaded,
			"model_name": self.model_name,
			"backend": self.backend,
			"adapter_path": self.adapter_path,
			"adapter_loaded": self.adapter_loaded,
			"load_error": self.load_error,
			"device": settings.DEVICE,
			"ollama_host": self.ollama_host,
			"fine_tuned": bool(self.adapter_loaded or (self.backend == "ollama" and str(self.model_name).startswith("resume-optimizer"))),
		}


model_manager = ModelManager()


class PromptTemplates:
	"""Prompt templates for resume optimization."""

	@staticmethod
	def full_optimization(resume_text, jd_text, company_name, target_role, candidate_evidence, strategy):
		supported_keywords_str = ""
		if candidate_evidence:
			try:
				evidence = json.loads(candidate_evidence) if isinstance(candidate_evidence, str) else candidate_evidence
				supported_keywords_str = ", ".join(
					set(
						evidence.get("explicit_skills", []) +
						evidence.get("project_skills", []) +
						evidence.get("experience_skills", []) +
						evidence.get("technologies", []) +
						evidence.get("tools", [])
					)
				)[:500]
			except Exception:
				supported_keywords_str = ""

		user_prompt = f"""COMPANY:
{company_name}

TARGET ROLE:
{target_role}

JOB DESCRIPTION:
{jd_text[:2000]}

ORIGINAL RESUME:
{resume_text[:2500]}

SUPPORTED JD KEYWORDS:
{supported_keywords_str if supported_keywords_str else "None explicitly mapped"}

STRATEGY:
{strategy}

Rewrite this into a one-page resume.
Keep the candidate's real summary, employers, dates, projects, and metrics.
Do not invent jobs, skills, or a sentence that says they are targeting this company.
Section order: PROFESSIONAL SUMMARY, TECHNICAL SKILLS, PROFESSIONAL EXPERIENCE, INTERNSHIP EXPERIENCE, PROJECTS, EDUCATION, CERTIFICATIONS, ACHIEVEMENTS.
Skills stay on labeled lines only: Languages, Core CS, Frontend, Backend, Databases, AI/ML & GenAI, Tools & Cloud.
No Other line. No project sentences inside skills.
Output ONLY the resume.

OUTPUT ONLY THE RESUME."""

		return [
			{"role": "system", "content": SYSTEM_RULES},
			{"role": "user", "content": user_prompt},
		]

	@staticmethod
	def extract_jd(jd_text):
		return f"""Extract structured information from this job description. Output ONLY valid JSON:

{{
	"required_skills": ["<must-have skills>"],
	"preferred_skills": ["<nice-to-have skills>"],
	"technologies": ["<technologies mentioned>"],
	"tools": ["<tools mentioned>"],
	"responsibilities": ["<key responsibilities>"],
	"domain_terms": ["<industry/domain terminology>"],
	"role_terminology": ["<role-specific terms>"],
	"important_keywords": ["<keywords that matter>"],
	"education_requirements": ["<education requirements>"],
	"experience_requirements": ["<experience requirements>"]
}}

Job Description:
{jd_text[:5000]}"""

	@staticmethod
	def extract_evidence(resume_text):
		return f"""Extract structured evidence from this resume. Output ONLY valid JSON:

{{
	"explicit_skills": ["<skills explicitly listed>"],
	"project_skills": ["<skills demonstrated in projects>"],
	"experience_skills": ["<skills demonstrated in work experience>"],
	"technologies": ["<technologies mentioned>"],
	"tools": ["<tools mentioned>"],
	"projects": ["<project names>"],
	"employers": ["<company names>"],
	"titles": ["<job titles>"],
	"education": ["<degrees, institutions>"],
	"certifications": ["<certifications>"],
	"achievements": ["<notable achievements>"],
	"metrics": ["<numbers, percentages, metrics>"]
}}

Resume:
{resume_text[:5000]}"""

	@staticmethod
	def safety_check(original_text, optimized_text):
		return f"""Compare the original resume and the optimized resume. Check if the optimized version adds ANY fact not present in the original.

Output ONLY valid JSON:
{{
	"passed": true,
	"added_facts": [],
	"hallucinations": []
}}

Rules:
- If every fact in the optimized version exists in the original, passed=true.
- If new employers, titles, dates, degrees, certifications, metrics, or skills were added that are not in the original, passed=false and list them.

Original Resume:
{original_text[:3000]}

Optimized Resume:
{optimized_text[:3000]}"""
