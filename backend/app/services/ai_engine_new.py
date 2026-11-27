"""
AI Engine: manages the local LLM ( + LoRA).
Falls back gracefully when no model is available.
"""

import json
import os
from typing import Optional

from app.core.config import settings


class ModelManager:
	"""Singleton that loads with 4-bit NF4 quantization + LoRA adapter."""

	def __init__(self):
		self.model = None
		self.tokenizer = None
		self.is_loaded = False
		self.load_error = None
		self.model_name = os.environ.get("BASE_MODEL", "/")
		self.adapter_path = os.environ.get("ADAPTER_PATH", "")

	def load(self) -> None:
		"""Load model with 4-bit NF4 quantization and optional LoRA adapter."""
		if self.is_loaded:
			return

		model_name = os.environ.get("BASE_MODEL", "/")
		adapter_path = os.environ.get("ADAPTER_PATH", "")
		device = os.environ.get("DEVICE", "cuda")

		if not model_name:
			self.is_loaded = False
			self.load_error = "No model name configured"
			return

		try:
			from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
			import torch

			print(f"Loading base model: {model_name}")
			bnb_config = BitsAndBytesConfig(
				load_in_4bit=True,
				bnb_4bit_quant_type="nf4",
				bnb_4bit_use_double_quant=True,
				bnb_4bit_compute_dtype=torch.float16,
			)

			self.tokenizer = AutoTokenizer.from_pretrained(
				model_name,
				trust_remote_code=True,
			)
			if self.tokenizer.pad_token is None:
				self.tokenizer.pad_token = self.tokenizer.eos_token

			self.model = AutoModelForCausalLM.from_pretrained(
				model_name,
				quantization_config=bnb_config,
				device_map="auto",
				torch_dtype=torch.float16,
				trust_remote_code=True,
			)

			# Load LoRA adapter if available
			if adapter_path and os.path.exists(adapter_path):
				print(f"Loading LoRA adapter from: {adapter_path}")
				from peft import PeftModel
				self.model = PeftModel.from_pretrained(self.model, adapter_path)
				print("LoRA adapter loaded successfully")
			else:
				print("No LoRA adapter found, using base model only")

			self.model.eval()
			self.is_loaded = True
			self.load_error = None
			print(f"Model ready on device: {device}")
		except Exception as e:
			self.is_loaded = False
			self.load_error = str(e)
			print(f"Model loading failed: {e}")

	async def generate(self, prompt: str, max_new_tokens: int = 1024, temperature: float = 0.7) -> str:
		"""Generate text from prompt using loaded model."""
		if not self.is_loaded or not self.model:
			return ""

		try:
			import torch

			# Use chat template if tokenizer supports it
			if hasattr(self.tokenizer, 'apply_chat_template'):
				messages = [{"role": "user", "content": prompt}]
				inputs = self.tokenizer.apply_chat_template(
					messages,
					tokenize=True,
					return_tensors="pt",
					add_generation_prompt=True,
				)
				inputs = {"input_ids": inputs.to(self.model.device)}
			else:
				inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

			with torch.no_grad():
				outputs = self.model.generate(
					**inputs,
					max_new_tokens=max_new_tokens,
					temperature=temperature,
					do_sample=temperature > 0,
					pad_token_id=self.tokenizer.eos_token_id,
					eos_token_id=self.tokenizer.eos_token_id,
				)

			# Decode only the new tokens (skip the prompt)
			input_len = inputs["input_ids"].shape[1] if isinstance(inputs, dict) else inputs.shape[1]
			generated = self.tokenizer.decode(
				outputs[0][input_len:],
				skip_special_tokens=True,
			)
			return generated.strip()
		except Exception as e:
			print(f"Generation failed: {e}")
			return ""

	def unload(self) -> None:
		"""Free model from memory."""
		if self.model:
			del self.model
			self.model = None
		if self.tokenizer:
			del self.tokenizer
			self.tokenizer = None
		self.is_loaded = False

	def get_status(self) -> dict:
		"""Return model status for health checks."""
		return {
			"model_loaded": self.is_loaded,
			"model_name": self.model_name,
			"adapter_path": self.adapter_path,
			"adapter_loaded": bool(self.adapter_path and os.path.exists(self.adapter_path)),
			"load_error": self.load_error,
			"device": os.environ.get("DEVICE", "cuda"),
		}


# Global singleton
model_manager = ModelManager()


class PromptTemplates:
	"""Prompt templates for resume optimization, matching notebook cells 39-55."""

	@staticmethod
	def full_optimization(resume_text, jd_text, company_name, target_role, candidate_evidence, strategy):
		"""Build optimization prompt matching notebook cell 51."""
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

		return f"""You are an expert ATS resume optimizer.

COMPANY:
{company_name}

TARGET ROLE:
{target_role}

JOB DESCRIPTION:
{jd_text[:5000]}

ORIGINAL RESUME:
{resume_text[:5000]}

CANDIDATE EVIDENCE:
{candidate_evidence[:3000] if candidate_evidence else "N/A"}

SUPPORTED JD KEYWORDS:
{supported_keywords_str if supported_keywords_str else "None explicitly mapped"}

STRICT RULES:
1. Never invent experience.
2. Never invent projects.
3. Never invent employers.
4. Never invent job titles.
5. Never invent certifications.
6. Never invent education.
7. Never invent achievements.
8. Never invent metrics or numbers.
9. Never claim a technology or skill unless it appears in the resume or is clearly demonstrated by existing project/experience evidence.
10. You may improve wording, grammar, structure and clarity.
11. You may naturally incorporate supported JD keywords.
12. Do not copy the job description blindly.
13. Preserve the candidate's actual experience.
14. Make the resume ATS-friendly.
15. Keep it concise and professional.
16. Prefer a one-page resume.
17. Use standard resume sections.
18. Do not use tables, graphics, icons or skill bars.
19. Do not include explanations outside the resume.
20. Do not mention these instructions.

TASK:
Create an enhanced version of the candidate's resume specifically aligned to the target role and job description.

OUTPUT ONLY THE RESUME."""

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
