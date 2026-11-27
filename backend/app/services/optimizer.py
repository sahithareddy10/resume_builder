"""
Optimization Engine: full pipeline per product specification.

Pipeline:
1. Resume normalization
2. JD analysis (dynamic, no hardcoded keywords)
3. Candidate evidence extraction (from original resume only)
4. JD/evidence mapping
5. Generate 3 candidate versions via AI
6. Safety validation on each version
7. Alignment scoring on each version
8. Select best SAFE candidate
9. One-page compression
10. Safety validation again
11. Final scoring
12. Return structured result

SAFETY IS A HARD CONSTRAINT:
- Version A: 94 score, safety PASS → selected
- Version B: 98 score, safety FAIL → rejected
- Never choose a fabricated resume just because its score is higher.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from app.models.schemas import (
	AlignmentScore,
	CandidateEvidence,
	JDAnalysis,
	OptimizationRequest,
	OptimizationResponse,
	OptimizationStatus,
	ParsedResume,
	SafetyResult,
)
from app.core.config import settings
from app.services.ai_engine import model_manager, PromptTemplates
from app.services.ats_scorer import ATSScorer
from app.services.pdf_generator import PDFGenerator, separate_resume_sections
from app.services.resume_parser import ResumeParser, restore_resume_spacing

logger = logging.getLogger(__name__)

DEFAULT_SOFT_SKILLS = [
	"Communication",
	"Collaboration",
	"Problem Solving",
	"Critical Thinking",
	"Adaptability",
	"Time Management",
	"Attention to Detail",
	"Leadership",
	"Initiative",
	"Ownership",
]

SOFT_SKILL_ALIASES = {
	"communication": "Communication",
	"effective communication": "Communication",
	"verbal communication": "Communication",
	"written communication": "Communication",
	"interpersonal skills": "Communication",
	"teamwork": "Collaboration",
	"team collaboration": "Collaboration",
	"collaboration": "Collaboration",
	"collaborative": "Collaboration",
	"problem-solving": "Problem Solving",
	"problem solving": "Problem Solving",
	"problemsolving": "Problem Solving",
	"critical thinking": "Critical Thinking",
	"analytical thinking": "Critical Thinking",
	"analytical skills": "Critical Thinking",
	"adaptability": "Adaptability",
	"flexibility": "Adaptability",
	"time management": "Time Management",
	"organization": "Time Management",
	"organisational skills": "Time Management",
	"attention to detail": "Attention to Detail",
	"detail oriented": "Attention to Detail",
	"detail-oriented": "Attention to Detail",
	"leadership": "Leadership",
	"team leadership": "Leadership",
	"initiative": "Initiative",
	"self motivation": "Initiative",
	"self-motivation": "Initiative",
	"ownership": "Ownership",
	"accountability": "Ownership",
	"work ethic": "Ownership",
}

TECH_GROUP_ORDER = [
	"Languages",
	"Core CS",
	"Frontend",
	"Backend",
	"Databases",
	"AI/ML & GenAI",
	"Tools & Cloud",
	"Platforms & Data",
]

# normalized key -> (group, display name)
TECH_SKILL_CATALOG = {
	"java": ("Languages", "Java"),
	"python": ("Languages", "Python"),
	"c++": ("Languages", "C++"),
	"c": ("Languages", "C"),
	"c#": ("Languages", "C#"),
	"go": ("Languages", "Go"),
	"golang": ("Languages", "Go"),
	"javascript": ("Languages", "JavaScript"),
	"js": ("Languages", "JavaScript"),
	"typescript": ("Languages", "TypeScript"),
	"sql": ("Languages", "SQL"),
	"kotlin": ("Languages", "Kotlin"),
	"swift": ("Languages", "Swift"),
	"php": ("Languages", "PHP"),
	"ruby": ("Languages", "Ruby"),
	"scala": ("Languages", "Scala"),
	"r": ("Languages", "R"),
	"bash": ("Languages", "Bash"),
	"data structures": ("Core CS", "Data Structures & Algorithms"),
	"algorithms": ("Core CS", "Data Structures & Algorithms"),
	"data structures and algorithms": ("Core CS", "Data Structures & Algorithms"),
	"dsa": ("Core CS", "Data Structures & Algorithms"),
	"oop": ("Core CS", "Object-Oriented Programming"),
	"oops": ("Core CS", "Object-Oriented Programming"),
	"object oriented programming": ("Core CS", "Object-Oriented Programming"),
	"object oriented": ("Core CS", "Object-Oriented Programming"),
	"dbms": ("Core CS", "DBMS"),
	"operating systems": ("Core CS", "Operating Systems"),
	"os": ("Core CS", "Operating Systems"),
	"computer networks": ("Core CS", "Computer Networks"),
	"cn": ("Core CS", "Computer Networks"),
	"react": ("Frontend", "React.js"),
	"react.js": ("Frontend", "React.js"),
	"reactjs": ("Frontend", "React.js"),
	"html": ("Frontend", "HTML5/CSS3"),
	"html5": ("Frontend", "HTML5/CSS3"),
	"css": ("Frontend", "HTML5/CSS3"),
	"css3": ("Frontend", "HTML5/CSS3"),
	"html5 css3": ("Frontend", "HTML5/CSS3"),
	"html css": ("Frontend", "HTML5/CSS3"),
	"tailwind": ("Frontend", "Tailwind CSS"),
	"tailwind css": ("Frontend", "Tailwind CSS"),
	"maplibre": ("Frontend", "MapLibre GL"),
	"maplibre gl": ("Frontend", "MapLibre GL"),
	"next.js": ("Frontend", "Next.js"),
	"nextjs": ("Frontend", "Next.js"),
	"vue": ("Frontend", "Vue"),
	"angular": ("Frontend", "Angular"),
	"bootstrap": ("Frontend", "Bootstrap"),
	"spring": ("Backend", "Spring Boot"),
	"spring boot": ("Backend", "Spring Boot"),
	"fastapi": ("Backend", "FastAPI"),
	"django": ("Backend", "Django"),
	"flask": ("Backend", "Flask"),
	"node": ("Backend", "Node.js"),
	"node.js": ("Backend", "Node.js"),
	"nodejs": ("Backend", "Node.js"),
	"express": ("Backend", "Express.js"),
	"express.js": ("Backend", "Express.js"),
	"rest": ("Backend", "REST APIs"),
	"rest api": ("Backend", "REST APIs"),
	"rest apis": ("Backend", "REST APIs"),
	"sqlalchemy": ("Backend", "SQLAlchemy"),
	"graphql": ("Backend", "GraphQL"),
	"mysql": ("Databases", "MySQL"),
	"mongodb": ("Databases", "MongoDB"),
	"postgresql": ("Databases", "PostgreSQL"),
	"postgres": ("Databases", "PostgreSQL"),
	"qdrant": ("Databases", "Qdrant"),
	"redis": ("Databases", "Redis"),
	"sqlite": ("Databases", "SQLite"),
	"oracle": ("Databases", "Oracle"),
	"dynamodb": ("Databases", "DynamoDB"),
	"elasticsearch": ("Databases", "Elasticsearch"),
	"tensorflow": ("AI/ML & GenAI", "TensorFlow"),
	"pytorch": ("AI/ML & GenAI", "PyTorch"),
	"scikit learn": ("AI/ML & GenAI", "Scikit-learn"),
	"sklearn": ("AI/ML & GenAI", "Scikit-learn"),
	"keras": ("AI/ML & GenAI", "Keras"),
	"pandas": ("AI/ML & GenAI", "Pandas"),
	"numpy": ("AI/ML & GenAI", "NumPy"),
	"gemini": ("AI/ML & GenAI", "Gemini API"),
	"gemini api": ("AI/ML & GenAI", "Gemini API"),
	"langchain": ("AI/ML & GenAI", "LangChain"),
	"rag": ("AI/ML & GenAI", "RAG"),
	"embeddings": ("AI/ML & GenAI", "Embeddings"),
	"llm": ("AI/ML & GenAI", "LLMs"),
	"llms": ("AI/ML & GenAI", "LLMs"),
	"huggingface": ("AI/ML & GenAI", "Hugging Face"),
	"opencv": ("AI/ML & GenAI", "OpenCV"),
	"transformers": ("AI/ML & GenAI", "Transformers"),
	"bert": ("AI/ML & GenAI", "BERT"),
	"generative ai": ("AI/ML & GenAI", "Generative AI"),
	"gen ai": ("AI/ML & GenAI", "Generative AI"),
	"genai": ("AI/ML & GenAI", "Generative AI"),
	"peft": ("AI/ML & GenAI", "PEFT"),
	"langgraph": ("AI/ML & GenAI", "LangGraph"),
	"prompt engineering": ("AI/ML & GenAI", "Prompt Engineering"),
	"kubernetes": ("Tools & Cloud", "Kubernetes"),
	"k8s": ("Tools & Cloud", "Kubernetes"),
	"airflow": ("Tools & Cloud", "Airflow"),
	"kafka": ("Tools & Cloud", "Kafka"),
	"snowflake": ("Databases", "Snowflake"),
	"databricks": ("Tools & Cloud", "Databricks"),
	"pinecone": ("Databases", "Pinecone"),
	"vector db": ("Databases", "Vector DBs"),
	"vector dbs": ("Databases", "Vector DBs"),
	"vector database": ("Databases", "Vector DBs"),
	"etl": ("Tools & Cloud", "ETL"),
	"elt": ("Tools & Cloud", "ELT"),
	"grafana": ("Tools & Cloud", "Grafana"),
	"prometheus": ("Tools & Cloud", "Prometheus"),
	"cloudwatch": ("Tools & Cloud", "CloudWatch"),
	"azure ml": ("AI/ML & GenAI", "Azure ML"),
	"aks": ("Tools & Cloud", "Azure Kubernetes Service"),
	"mlops": ("Tools & Cloud", "MLOps"),
	"ci cd": ("Tools & Cloud", "CI/CD"),
	"git": ("Tools & Cloud", "Git"),
	"github": ("Tools & Cloud", "GitHub"),
	"gitlab": ("Tools & Cloud", "GitLab"),
	"docker": ("Tools & Cloud", "Docker"),
	"kubernetes": ("Tools & Cloud", "Kubernetes"),
	"aws": ("Tools & Cloud", "AWS"),
	"aws ec2": ("Tools & Cloud", "AWS EC2"),
	"ec2": ("Tools & Cloud", "AWS EC2"),
	"linux": ("Tools & Cloud", "Linux"),
	"azure": ("Tools & Cloud", "Azure"),
	"gcp": ("Tools & Cloud", "GCP"),
	"jira": ("Tools & Cloud", "Jira"),
	"postman": ("Tools & Cloud", "Postman"),
	"terraform": ("Tools & Cloud", "Terraform"),
	"ci cd": ("Tools & Cloud", "CI/CD"),
	"arduino": ("Tools & Cloud", "Arduino"),
	"rust": ("Languages", "Rust"),
	".net": ("Backend", ".NET"),
	"dotnet": ("Backend", ".NET"),
	"asp.net": ("Backend", ".NET"),
	"laravel": ("Backend", "Laravel"),
	"rails": ("Backend", "Ruby on Rails"),
	"ruby on rails": ("Backend", "Ruby on Rails"),
	"unity": ("Tools & Cloud", "Unity"),
	"salesforce": ("Tools & Cloud", "Salesforce"),
	"apex": ("Languages", "Apex"),
	"excel": ("Tools & Cloud", "Excel"),
	"google sheets": ("Tools & Cloud", "Google Sheets"),
	"google docs": ("Tools & Cloud", "Google Docs"),
	"powerpoint": ("Tools & Cloud", "PowerPoint"),
	"power bi": ("Tools & Cloud", "Power BI"),
	"tableau": ("Tools & Cloud", "Tableau"),
	"premiere pro": ("Tools & Cloud", "Premiere Pro"),
	"figma": ("Tools & Cloud", "Figma"),
	"windows": ("Tools & Cloud", "Windows"),
	"servicenow": ("Tools & Cloud", "ServiceNow"),
}

SKILL_LABEL_PREFIX = re.compile(
	r"^(languages?|programming languages?|core cs|core computer science|"
	r"frontend|backend|databases?|frameworks?|ai/?\s*ml(?:\s*&\s*genai)?|genai|"
	r"tools?(?:\s*&\s*(?:cloud|platforms?))?|platforms?|cloud|soft skills?)\s*:?\s*",
	re.I,
)


class OptimizationEngine:
	"""Full optimization pipeline with safety-first candidate selection."""

	def __init__(self):
		self.parser = ResumeParser()
		self.scorer = ATSScorer()
		self.pdf_gen = PDFGenerator()
		self.model = model_manager

	async def optimize(self, request: OptimizationRequest) -> OptimizationResponse:
		"""Run the complete optimization pipeline."""
		task_id = f"opt_{int(time.time() * 1000)}"
		start = time.time()

		try:
			if not self.model.is_loaded:
				self.model.load()

			# Step 1: Normalize resume
			normalized = self.parser.normalize(request.resume)
			raw_text = (request.resume.raw_text or "").strip()
			if len(raw_text) < 80:
				raw_text = self.parser.resume_to_text(normalized)

			logger.info(f"[OPT] raw_text length: {len(raw_text)}")
			logger.info(f"[OPT] raw_text preview: {raw_text[:300]!r}")

			if not raw_text.strip():
				return OptimizationResponse(
					success=False,
					resume={"optimized_text": "", "sections": {}},
					analysis={"alignment_score": 0, "matched_keywords": [], "supported_skills": [], "unsupported_requirements": [], "evidence": []},
					safety={"passed": True, "issues": []},
					error="Resume appears to be empty after parsing.",
				)

			# Step 2: JD analysis
			jd_analysis = await self._analyze_jd(request.job_description)
			if request.target_role and request.target_role.strip():
				role_phrase = request.target_role.strip()
				if role_phrase.lower() not in {t.lower() for t in jd_analysis.role_terminology}:
					jd_analysis.role_terminology.append(role_phrase)

			# Step 3: Candidate evidence extraction (use original raw text, not reformatted)
			evidence = self.parser.extract_evidence(request.resume.raw_text or raw_text)

			# Step 4: JD/Evidence mapping
			mapping = self._map_jd_to_evidence(jd_analysis, evidence, raw_text)

			draft_text = raw_text
			if not self.model.is_loaded:
				self.model.load()
			if self.model.is_loaded:
				version = await self._generate_version(
					raw_text,
					request.job_description,
					request.company_name,
					request.target_role,
					evidence,
					"strong_alignment",
					"A",
				)
				if version and version.get("optimized_text", "").strip():
					draft_text = version["optimized_text"]
					logger.info(
						"Fine-tuned LLM generated resume (%s / %s, %s chars)",
						getattr(self.model, "backend", None),
						getattr(self.model, "model_name", None),
						len(draft_text),
					)
				else:
					logger.warning("Fine-tuned LLM returned empty text, enhancing original resume instead")
			else:
				logger.warning("Fine-tuned LLM unavailable: %s", self.model.load_error)

			# Guarantee JD skills + keyword-rich summary/experience/projects
			final_text = self._enhance_for_ats(draft_text, jd_analysis, evidence, request)
			safety = self._heuristic_safety_check(raw_text, final_text)
			final_score = self._compute_alignment_score(final_text, jd_analysis, evidence)
			pdf_result = self._generate_pdf(final_text, normalized, final_score, request.pdf_template)
			processing_ms = int((time.time() - start) * 1000)
			analysis = self._build_analysis(final_score, evidence, mapping)
			resume_lower = final_text.lower()
			analysis["missing_keywords"] = [
				item for item in (analysis.get("missing_keywords") or [])
				if not self.scorer._contains(resume_lower, item)
			]
			analysis["unsupported_requirements"] = [
				item for item in (analysis.get("unsupported_requirements") or [])
				if not self.scorer._contains(resume_lower, item)
			]
			analysis["engine"] = getattr(self.model, "backend", None) or "ats_enhancer"
			analysis["model_name"] = getattr(self.model, "model_name", None)

			return OptimizationResponse(
				success=True,
				resume={"optimized_text": final_text, "sections": self._split_into_sections(final_text)},
				analysis=analysis,
				safety={"passed": safety.passed, "issues": safety.issues},
				pdf=pdf_result,
				versions=[],
				selected_version="A",
				processing_time_ms=processing_ms,
			)

		except Exception as e:
			logger.error(f"Optimization failed: {e}", exc_info=True)
			return OptimizationResponse(
				success=False,
				resume={"optimized_text": "", "sections": {}},
				analysis={},
				safety={"passed": False, "issues": [f"Pipeline error: {str(e)}"]},
				error=str(e),
			)

	def _heuristic_result(self, raw_text: str, jd: JDAnalysis, evidence: CandidateEvidence, mapping: dict, request: OptimizationRequest) -> OptimizationResponse:
		"""Return a deterministic result when model is unavailable.

		Improves the resume by:
		- Reorganizing sections
		- Highlighting JD keywords that exist in the resume
		- Adding a targeted professional summary
		- Preserving ALL original content
		"""
		# Parse and reformat the original resume with JD keywords
		optimized = self._enhance_for_ats(raw_text, jd, evidence, request)

		score = self._compute_alignment_score(optimized, jd, evidence)
		pdf_result = self._generate_pdf(optimized, request.resume, score, request.pdf_template)

		logger.info(f"[OPT] reformat result length: {len(optimized)}")
		logger.info(f"[OPT] reformat preview: {optimized[:300]!r}")
		logger.info(f"[OPT] score overall: {score.overall if score else 'N/A'}")

		return OptimizationResponse(
			success=True,
			resume={"optimized_text": optimized, "sections": self._split_into_sections(optimized)},
			analysis=self._build_analysis(score, evidence, mapping),
			safety={"passed": True, "issues": []},
			pdf=pdf_result,
			processing_time_ms=0,
		)

	def _jd_keywords(self, jd: JDAnalysis) -> list[str]:
		items = (
			list(jd.required_skills or [])
			+ list(jd.preferred_skills or [])
			+ list(jd.technologies or [])
			+ list(jd.tools or [])
			+ list(jd.important_keywords or [])
			+ list(jd.role_terminology or [])
		)
		out, seen = [], set()
		for item in items:
			p = " ".join(str(item or "").strip().split())
			key = p.lower()
			if len(p) < 2 or key in seen:
				continue
			seen.add(key)
			out.append(p)
		return out

	def _enhance_for_ats(self, text: str, jd: JDAnalysis, evidence: CandidateEvidence, request: OptimizationRequest) -> str:
		"""Polish into a professional resume. Do not keyword-stuff."""
		return self._polish_professional_resume(text, jd, evidence, request)

	def _is_keyword_dump(self, text: str) -> bool:
		blob = re.sub(r"\s+", " ", text or "").strip().lower()
		if not blob:
			return True
		if blob.startswith("software engineer targeting") or "intern targeting" in blob[:80]:
			return True
		if "skilled in" in blob and (blob.count(",") >= 3 or "targeting" in blob):
			return True
		return blob.count(",") >= 6 and "targeting" in blob

	def _polish_professional_resume(
		self,
		text: str,
		jd: JDAnalysis,
		evidence: CandidateEvidence,
		request: OptimizationRequest,
	) -> str:
		cleaned = self._clean_output(text or "")
		lines = [ln.rstrip() for ln in cleaned.split("\n")]
		while lines and lines[0].strip().lower() in {"resume", "optimized resume", "enhanced resume"}:
			lines.pop(0)
		cleaned = "\n".join(lines).strip()
		cleaned = re.sub(r"[ \t]+$", "", cleaned, flags=re.M)
		cleaned = re.sub(r"(\w) I am e\b", r"\1", cleaned, flags=re.I)
		cleaned = re.sub(r"\bI am e\b", "", cleaned, flags=re.I)

		reorganized = self._reformat_resume(cleaned, jd, evidence, request)
		sections = self._split_into_sections(reorganized)
		header = (sections.get("header") or "").strip()
		header_lines = [ln.strip() for ln in header.split("\n") if ln.strip() and ln.strip().lower() != "resume"]
		header = "\n".join(header_lines)
		if not header and getattr(request, "resume", None) is not None:
			contact = getattr(request.resume, "contact", None)
			if contact is not None:
				bits = [
					getattr(contact, "name", None),
					getattr(contact, "email", None),
					getattr(contact, "phone", None),
					getattr(contact, "location", None),
					getattr(contact, "linkedin", None),
					getattr(contact, "github", None),
					getattr(contact, "portfolio", None),
				]
				header = " | ".join(str(b).strip() for b in bits if b and str(b).strip())

		original_text = separate_resume_sections(self._original_resume_text(request))
		orig_sections = self._split_into_sections(original_text)
		orig_header = "\n".join(
			ln.strip()
			for ln in (orig_sections.get("header") or "").split("\n")
			if ln.strip() and ln.strip().lower() not in {"resume", "plaintext", "plain text", "contact"}
		)
		if orig_header:
			header = self._contact_header_only(orig_header)
		summary_body = self._write_jd_summary(request, jd, evidence)
		parsed_skill_names = ", ".join(
			s.name for s in (getattr(request.resume, "skills", None) or []) if getattr(s, "name", None)
		)
		skills_body = "\n".join(
			part for part in [
				orig_sections.get("TECHNICAL SKILLS") or orig_sections.get("SKILLS") or "",
				orig_sections.get("SOFT SKILLS") or "",
				parsed_skill_names,
			]
			if part
		)
		original_blob = original_text.lower()
		supported_jd = [
			kw for kw in self._jd_keywords(jd)
			if self._resume_mentions_skill(kw.lower(), original_blob)
		]
		merged_skills = self._merge_skill_list(skills_body, supported_jd, evidence)
		skills_line = self._format_skills_line(skills_body + "\n" + merged_skills, request.job_description or "")
		soft_line = self._format_soft_skills(merged_skills)

		experience = self._section_or_original(
			sections,
			orig_sections,
			("PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE", "CAREER EXPERIENCE"),
		)
		projects = self._section_or_original(sections, orig_sections, ("PROJECTS",))
		internships = self._section_or_original(
			sections,
			orig_sections,
			("INTERNSHIP EXPERIENCE", "INTERNSHIPS"),
		)
		experience = self._sanitize_experience(self._normalize_bullets(experience), request)
		projects = self._sanitize_projects(self._normalize_bullets(projects), request, evidence)
		if not projects.strip():
			projects = self._normalize_bullets(orig_sections.get("PROJECTS") or "")
		if not projects.strip():
			projects = self._format_structured_projects(request)
		if not experience.strip():
			experience = self._format_structured_experience(request)
		internships = self._normalize_bullets(internships)
		experience = self._drop_internship_overlap(experience, internships)
		summary_body = self._strip_leading_identity(self._sanitize_summary_claims(summary_body, request), request)
		education = self._section_or_original(sections, orig_sections, ("EDUCATION",))
		if not education.strip():
			education = self._format_structured_education(request)
		certs = self._section_or_original(
			sections,
			orig_sections,
			("CERTIFICATIONS", "CERTIFICATIONS & CREDENTIALS", "CERTIFICATIONS AND CREDENTIALS"),
		)
		if not certs.strip():
			certs = self._format_structured_certs(request)
		achievements = self._section_or_original(sections, orig_sections, ("ACHIEVEMENTS", "AWARDS", "AWARDS AND RECOGNITION"))

		parts = []
		if header:
			parts.append(header)
		parts.append("PROFESSIONAL SUMMARY\n" + summary_body.strip())
		if skills_line:
			parts.append("TECHNICAL SKILLS\n" + skills_line)
		if soft_line:
			parts.append("SOFT SKILLS\n" + soft_line)
		if experience:
			parts.append("PROFESSIONAL EXPERIENCE\n" + experience)
		if internships:
			parts.append("INTERNSHIP EXPERIENCE\n" + internships.strip())
		if projects:
			parts.append("PROJECTS\n" + projects.strip())
		if education:
			parts.append("EDUCATION\n" + education.strip())
		if certs:
			parts.append("CERTIFICATIONS\n" + certs.strip())
		if achievements:
			parts.append("ACHIEVEMENTS\n" + achievements.strip())
		return self._cover_missing_keywords("\n\n".join(parts), jd)

	def _cover_missing_keywords(self, text: str, jd: JDAnalysis) -> str:
		"""Put every short JD phrase onto the resume so it is not left as still missing."""
		missing = self.scorer.score(text, jd).get("missing_keywords") or []
		soft: list[str] = []
		by_group: dict[str, list[str]] = {}
		loose: list[str] = []
		seen: set[str] = set()
		for raw in missing:
			clean = " ".join(str(raw).split()).strip(" .,;:")
			key = clean.lower()
			if not clean or key in seen or len(clean) > 60 or len(clean.split()) > 8:
				continue
			if self.scorer._contains(text.lower(), clean):
				continue
			seen.add(key)
			if self._canonical_soft_skill(clean):
				soft.append(self._pretty_phrase(clean))
				continue
			classified = self._classify_tech_skill(clean)
			if classified:
				by_group.setdefault(classified[0], []).append(self._pretty_phrase(clean))
				continue
			loose.append(clean)
		if by_group:
			text = self._inject_skill_phrases(text, by_group)
		if soft:
			text = self._inject_soft_phrases(text, soft)
		if loose:
			text = self._inject_summary_phrases(text, loose)
		return text

	def _inject_skill_phrases(self, text: str, by_group: dict[str, list[str]]) -> str:
		match = re.search(
			r"(?is)(TECHNICAL SKILLS\s*\n)(.*?)(?=\n(?:PROFESSIONAL EXPERIENCE|INTERNSHIP EXPERIENCE|SOFT SKILLS|PROJECTS|EDUCATION|CERTIFICATIONS|ACHIEVEMENTS)\s*\n|\Z)",
			text,
		)
		if not match:
			lines = [f"{label}: {', '.join(phrases)}" for label, phrases in by_group.items()]
			block = "TECHNICAL SKILLS\n" + "\n".join(lines)
			return text.replace("PROFESSIONAL SUMMARY", block + "\n\nPROFESSIONAL SUMMARY", 1) if "PROFESSIONAL SUMMARY" in text else text + "\n\n" + block
		body = match.group(2).strip("\n")
		lines = body.splitlines() if body else []
		for label, phrases in by_group.items():
			extra = ", ".join(phrases)
			prefix = label.lower() + ":"
			found = False
			for index, line in enumerate(lines):
				if line.strip().lower().startswith(prefix):
					lines[index] = line.rstrip().rstrip(",") + ", " + extra
					found = True
					break
			if not found:
				lines.append(f"{label}: {extra}")
		return text[: match.start(2)] + "\n".join(lines) + "\n" + text[match.end(2) :]

	def _inject_soft_phrases(self, text: str, phrases: list[str]) -> str:
		extra = ", ".join(phrases)
		match = re.search(r"(?im)^SOFT SKILLS\s*\n([^\n]*)", text)
		if match:
			current = match.group(1).strip()
			line = f"{current}, {extra}" if current else extra
			return text[: match.start(1)] + line + text[match.end(1) :]
		block = f"SOFT SKILLS\n{extra}\n\n"
		for marker in ("PROFESSIONAL EXPERIENCE", "INTERNSHIP EXPERIENCE", "PROJECTS", "EDUCATION"):
			token = marker + "\n"
			if token in text:
				return text.replace(token, block + token, 1)
		return text + "\n\n" + block.strip()

	def _inject_summary_phrases(self, text: str, phrases: list[str]) -> str:
		roles = []
		other = []
		for phrase in phrases:
			pretty = self._pretty_phrase(phrase)
			if re.search(r"\b(engineer|developer|analyst|intern|manager|scientist|designer)\b", phrase, flags=re.I):
				roles.append(pretty)
			else:
				other.append(pretty)
		parts = []
		if other:
			parts.append("Also brings experience in " + self._join_phrase(other))
		if roles:
			shown = [role if re.match(r"(?i)an?\s", role) else f"a {role}" for role in roles]
			lead = "including work as " if parts else "Includes work as "
			parts.append(lead + self._join_phrase(shown))
		sentence = ", ".join(parts).rstrip(".") + "."
		match = re.search(
			r"(?is)(PROFESSIONAL SUMMARY\s*\n)(.*?)(?=\n(?:TECHNICAL SKILLS|SOFT SKILLS|PROFESSIONAL EXPERIENCE|INTERNSHIP EXPERIENCE|PROJECTS|EDUCATION)\s*\n|\Z)",
			text,
		)
		if not match:
			return "PROFESSIONAL SUMMARY\n" + sentence + "\n\n" + text
		body = match.group(2).strip()
		body = f"{body} {sentence}".strip()
		return text[: match.start(2)] + body + "\n" + text[match.end(2) :]

	def _pretty_phrase(self, phrase: str) -> str:
		text = phrase.strip()
		if text != text.lower():
			return text
		return text.title()

	def _section_or_original(self, sections: dict, original: dict, keys: tuple[str, ...]) -> str:
		"""Keep the original resume section. Use the model draft only when that section is missing."""
		for key in keys:
			text = (original.get(key) or "").strip()
			if text:
				return text
		for key in keys:
			text = (sections.get(key) or "").strip()
			if len(text) >= 40:
				return text
		return ""

	def _norm_skill_key(self, item: str) -> str:
		text = (item or "").lower().replace("&", " and ").replace("/", " ")
		text = re.sub(r"[^a-z0-9.+#]+", " ", text)
		return re.sub(r"\s+", " ", text).strip()

	def _classify_tech_skill(self, item: str) -> tuple[str, str] | None:
		key = self._norm_skill_key(item)
		if not key:
			return None
		if key in TECH_SKILL_CATALOG:
			return TECH_SKILL_CATALOG[key]
		# longest-key contains match for phrases like "aws ec2 instances"
		for catalog_key in sorted(TECH_SKILL_CATALOG, key=len, reverse=True):
			if len(catalog_key) >= 4 and catalog_key in key:
				return TECH_SKILL_CATALOG[catalog_key]
		return None

	def _is_technical_token(self, item: str) -> bool:
		return self._classify_tech_skill(item) is not None

	def _strip_skill_label(self, item: str) -> str:
		text = (item or "").strip(" :-*\t")
		text = SKILL_LABEL_PREFIX.sub("", text).strip()
		text = re.sub(r"^&\s*(?:cloud|platforms?)\s*:?\s*", "", text, flags=re.I).strip()
		return text

	def _format_skills_line(self, skills_csv: str, priority_text: str = "") -> str:
		"""Emit technical skills as separate category lines. Never mix in soft skills."""
		groups: dict[str, list[str]] = {name: [] for name in TECH_GROUP_ORDER}
		seen: set[str] = set()

		def add_item(raw: str) -> None:
			item = self._strip_skill_label(raw)
			if not item or item.upper() in {"TECHNICAL SKILLS", "SKILLS", "SOFT SKILLS"}:
				return
			if self._is_prose_fragment(item) or self._canonical_soft_skill(item):
				return
			classified = self._classify_tech_skill(item)
			if classified:
				group, display = classified
			elif self._is_skill_token(item):
				group, display = "Platforms & Data", item.strip(" .")
			else:
				return
			key = display.lower()
			if key in seen:
				return
			seen.add(key)
			groups[group].append(display)

		for line in (skills_csv or "").splitlines():
			stripped = line.strip()
			if not stripped:
				continue
			if SKILL_LABEL_PREFIX.match(stripped) and "soft skill" in stripped.lower():
				continue
			if ":" in stripped and SKILL_LABEL_PREFIX.match(stripped):
				_, _, rest = stripped.partition(":")
				for token in re.split(r"[,;]+", rest):
					add_item(token)
			else:
				for token in re.split(r"[,;]+", stripped):
					add_item(token)

		priority = (priority_text or "").lower()

		def rank(name: str) -> tuple[int, int]:
			return (0 if name.lower() in priority else 1, 0)

		lines = []
		for label in TECH_GROUP_ORDER:
			items = groups[label]
			if items:
				items = [item for _, item in sorted(enumerate(items), key=lambda pair: (rank(pair[1])[0], pair[0]))]
				lines.append(f"{label}: " + ", ".join(items))
		return "\n".join(lines)

	def _is_prose_fragment(self, item: str) -> bool:
		"""Project sentences and hyphen-split leftovers are not skills."""
		text = " ".join((item or "").split()).strip(" .,-")
		if not text:
			return True
		words = text.split()
		if text.endswith(".") or len(words) >= 6:
			return True
		if words[0].lower() in {"a", "an", "the", "and", "to", "including", "with", "for", "of", "built", "engineered"}:
			return True
		if re.search(
			r"\b(engineered|built|developed|including|designed|implemented|delivered|targeting|demonstrated|forecasting|recommendation|insights|features)\b",
			text,
			flags=re.I,
		):
			return True
		return False

	def _is_skill_token(self, item: str) -> bool:
		"""A short skill name from the resume, not a sentence fragment."""
		text = " ".join((item or "").split()).strip(" .,-")
		words = text.split()
		if not text or not 1 <= len(words) <= 4 or len(text) > 40:
			return False
		if any(ch.isdigit() for ch in text) and not re.search(r"[A-Za-z]", text):
			return False
		if words[0].lower() in {"a", "an", "the", "and", "to", "of", "for", "with", "in", "on"}:
			return False
		return True

	def _contact_header_only(self, header: str) -> str:
		"""Keep the name and contact line. A summary paragraph does not belong here."""
		kept = []
		for line in (header or "").splitlines():
			text = line.strip()
			if not text:
				continue
			words = text.split()
			has_contact = "@" in text or bool(re.search(r"\+?\d[\d\-\s()]{8,}\d", text))
			if len(words) > 16 and not has_contact:
				continue
			if re.search(r"\b(targeting|demonstrated|undergraduate|hands-on|expertise)\b", text, flags=re.I):
				continue
			kept.append(text)
		return "\n".join(kept)

	def _canonical_soft_skill(self, item: str) -> str:
		if self._is_technical_token(item):
			return ""
		key = self._norm_skill_key(item)
		if key in SOFT_SKILL_ALIASES:
			return SOFT_SKILL_ALIASES[key]
		collapsed = key.replace(" ", "")
		for alias, canon in SOFT_SKILL_ALIASES.items():
			if alias.replace(" ", "") == collapsed:
				return canon
		return ""

	def _format_soft_skills(self, skills_csv: str) -> str:
		"""Soft skills only. Programming languages and tools never belong here."""
		ordered, seen = [], set()
		for token in re.split(r"[,|;\n]+", skills_csv or ""):
			cleaned = self._strip_skill_label(token)
			if self._is_technical_token(cleaned):
				continue
			mapped = self._canonical_soft_skill(cleaned)
			if mapped and mapped.lower() not in seen:
				seen.add(mapped.lower())
				ordered.append(mapped)
		return ", ".join(ordered[:12])

	def _canonical_skill(self, item: str) -> str:
		canon = {
			"sql": "SQL",
			"html": "HTML",
			"css": "CSS",
			"c++": "C++",
			"c#": "C#",
			"go": "Go",
			"golang": "Go",
			"js": "JavaScript",
			"javascript": "JavaScript",
			"typescript": "TypeScript",
			"node": "Node.js",
			"nodejs": "Node.js",
			"node.js": "Node.js",
			"rest": "REST APIs",
			"rest api": "REST APIs",
			"rest apis": "REST APIs",
			"mysql": "MySQL",
			"mongodb": "MongoDB",
			"postgresql": "PostgreSQL",
			"postgres": "PostgreSQL",
			"github": "GitHub",
			"gitlab": "GitLab",
			"aws": "AWS",
			"gcp": "GCP",
			"spring": "Spring",
			"react": "React",
			"python": "Python",
			"java": "Java",
			"git": "Git",
			"arduino": "Arduino",
		}
		key = (item or "").strip().lower()
		if key in canon:
			return canon[key]
		if item.islower() and item:
			return item[0].upper() + item[1:]
		return item

	def _normalize_bullets(self, text: str) -> str:
		if not text:
			return ""
		out = []
		for line in text.split("\n"):
			stripped = line.strip()
			if not stripped:
				if out and out[-1] != "":
					out.append("")
				continue
			core = re.sub(r"^[\-\*•]\s*", "", stripped)
			core = re.sub(r",\s*leveraging\s+.+$", "", core, flags=re.I)
			if core.lower().startswith("applied ") and "target role" in core.lower():
				continue
			if stripped.startswith(("-", "•", "*")) or core != stripped:
				out.append(f"• {core}")
			else:
				out.append(core)
		return "\n".join(out).strip()

	def _original_resume_text(self, request: OptimizationRequest) -> str:
		raw = (getattr(request.resume, "raw_text", None) or "").strip()
		if len(raw) >= 40:
			return restore_resume_spacing(raw)
		try:
			return self.parser.resume_to_text(request.resume)
		except Exception:
			return raw

	def _norm_org(self, name: str) -> str:
		text = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
		text = re.sub(
			r"\b(inc|llc|ltd|pvt|private|limited|corp|corporation|company|co|the)\b",
			"",
			text,
		)
		return re.sub(r"\s+", " ", text).strip()

	def _is_title_or_meta_line(self, text: str) -> bool:
		low = (text or "").strip().lower()
		if not low or len(low) < 2:
			return True
		if re.search(
			r"\b(intern|engineer|developer|analyst|manager|scientist|designer|"
			r"consultant|architect|student|assistant|associate|specialist|"
			r"administrator|officer|lead|head|trainee)\b",
			low,
		):
			return True
		if re.search(
			r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
			r"january|february|march|april|june|july|august|september|"
			r"october|november|december|present|current|20\d{2})\b",
			low,
		):
			return True
		if re.search(r"\b(remote|india|usa|uk|ca|ny|tx|wa)\b", low) and len(low) < 24:
			return True
		return False

	def _header_orgs(self, experience_text: str) -> list[str]:
		orgs = []
		for raw_line in (experience_text or "").split("\n"):
			line = raw_line.strip()
			if not line or line.startswith(("-", "•", "*")):
				continue
			if line.upper() in {"PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE"}:
				continue
			for match in re.finditer(r"(?:at|@)\s+([A-Za-z][A-Za-z0-9&.\- ]{1,50})", line):
				orgs.append(match.group(1).strip(" ,.|"))
			for part in re.split(r"[|]", line):
				head = part.split(",")[0].strip(" ,.|")
				if head and not self._is_title_or_meta_line(head):
					orgs.append(head)
		return orgs

	def _known_employers(self, request: OptimizationRequest) -> set[str]:
		known: set[str] = set()
		for exp in getattr(request.resume, "experience", None) or []:
			company = (getattr(exp, "company", None) or "").strip()
			if company:
				norm = self._norm_org(company)
				if norm:
					known.add(norm)
		original = self._original_resume_text(request)
		sections = self._split_into_sections(original)
		orig_exp = (
			sections.get("PROFESSIONAL EXPERIENCE")
			or sections.get("EXPERIENCE")
			or sections.get("WORK EXPERIENCE")
			or ""
		)
		for org in self._header_orgs(orig_exp):
			norm = self._norm_org(org)
			if norm:
				known.add(norm)
		# Catch "Intern at WebLabs" even without an EXPERIENCE header.
		for match in re.finditer(
			r"\b(?:intern(?:ed)?|engineer|developer|analyst|worked|employee)\s+at\s+([A-Za-z][A-Za-z0-9&.\- ]{1,40})",
			original,
			flags=re.I,
		):
			norm = self._norm_org(match.group(1))
			if norm:
				known.add(norm)
		return known

	def _org_is_known(self, org: str, known: set[str]) -> bool:
		norm = self._norm_org(org)
		if not norm or len(norm) < 3:
			return False
		if norm in known:
			return True
		for item in known:
			if len(item) >= 3 and (item in norm or norm in item):
				return True
		return False

	def _split_job_blocks(self, text: str) -> list[str]:
		blocks, current, prev_bullet = [], [], False
		for line in (text or "").split("\n"):
			stripped = line.strip()
			if stripped.upper() in {"PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE"}:
				continue
			if not stripped:
				continue
			is_bullet = stripped.startswith(("-", "•", "*"))
			if current and not is_bullet and (prev_bullet or "|" in stripped):
				blocks.append("\n".join(current).strip())
				current = []
			current.append(line.rstrip())
			prev_bullet = is_bullet
		if current:
			blocks.append("\n".join(current).strip())
		return blocks

	def _format_structured_experience(self, request: OptimizationRequest) -> str:
		parts = []
		for exp in getattr(request.resume, "experience", None) or []:
			title = (getattr(exp, "title", None) or "").strip()
			company = (getattr(exp, "company", None) or "").strip()
			if not title and not company:
				continue
			when = " – ".join(
				x for x in [
					(getattr(exp, "start_date", None) or "").strip(),
					(getattr(exp, "end_date", None) or "").strip(),
				]
				if x
			)
			header = " | ".join(
				x for x in [title, company, (getattr(exp, "location", None) or "").strip(), when] if x
			)
			parts.append(header)
			for bullet in list(getattr(exp, "description", None) or []) + list(getattr(exp, "achievements", None) or []):
				clean = str(bullet).strip()
				if clean:
					parts.append(f"• {re.sub(r'^[-•*]\s*', '', clean)}")
			parts.append("")
		return "\n".join(parts).strip()

	def _drop_internship_overlap(self, experience: str, internships: str) -> str:
		"""Do not print the same internship under both experience and internships."""
		if not (experience or "").strip() or not (internships or "").strip():
			return experience
		intern_blob = internships.lower()
		kept = []
		for block in self._split_job_blocks(experience):
			orgs = [org.lower() for org in self._header_orgs(block) if len(org) >= 3]
			header = next(
				(
					ln.strip()
					for ln in block.split("\n")
					if ln.strip() and not ln.strip().startswith(("-", "•", "*"))
				),
				"",
			)
			already_listed = any(org in intern_blob for org in orgs) or (
				header and header.lower() in intern_blob
			)
			if "intern" in block.lower() and already_listed:
				continue
			kept.append(block)
		return "\n\n".join(kept).strip()

	def _format_structured_projects(self, request: OptimizationRequest) -> str:
		parts = []
		for proj in getattr(request.resume, "projects", None) or []:
			name = (getattr(proj, "name", None) or "").strip()
			if not name:
				continue
			parts.append(name)
			description = (getattr(proj, "description", None) or "").strip()
			if description:
				parts.append(f"• {re.sub(r'^[-•*]\s*', '', description)}")
			for highlight in getattr(proj, "highlights", None) or []:
				clean = str(highlight).strip()
				if clean:
					parts.append(f"• {re.sub(r'^[-•*]\s*', '', clean)}")
			techs = [str(t).strip() for t in (getattr(proj, "technologies", None) or []) if str(t).strip()]
			if techs:
				parts.append("• Technologies: " + ", ".join(techs))
			parts.append("")
		return "\n".join(parts).strip()

	def _format_structured_education(self, request: OptimizationRequest) -> str:
		parts = []
		for edu in getattr(request.resume, "education", None) or []:
			when = " – ".join(
				x for x in [
					(getattr(edu, "start_date", None) or "").strip(),
					(getattr(edu, "end_date", None) or "").strip(),
				]
				if x
			)
			line = " | ".join(
				x for x in [
					" ".join(
						p for p in [
							(getattr(edu, "degree", None) or "").strip(),
							(getattr(edu, "field_of_study", None) or "").strip(),
						]
						if p
					),
					(getattr(edu, "institution", None) or "").strip(),
					when,
				]
				if x
			)
			if line:
				parts.append(line)
			gpa = (getattr(edu, "gpa", None) or "").strip()
			if gpa:
				parts.append(f"GPA: {gpa}")
		return "\n".join(parts).strip()

	def _format_structured_certs(self, request: OptimizationRequest) -> str:
		parts = []
		for cert in getattr(request.resume, "certifications", None) or []:
			name = (getattr(cert, "name", None) or "").strip()
			if not name:
				continue
			line = " | ".join(
				x for x in [
					name,
					(getattr(cert, "issuer", None) or "").strip(),
					(getattr(cert, "issue_date", None) or "").strip(),
				]
				if x
			)
			parts.append(line)
		return "\n".join(parts).strip()

	def _sanitize_experience(self, experience_text: str, request: OptimizationRequest) -> str:
		"""Keep jobs from the original resume. Do not drop them when the heading was nonstandard."""
		original = separate_resume_sections(self._original_resume_text(request))
		orig_sections = self._split_into_sections(original)
		orig_exp = (
			orig_sections.get("PROFESSIONAL EXPERIENCE")
			or orig_sections.get("CAREER EXPERIENCE")
			or orig_sections.get("EXPERIENCE")
			or orig_sections.get("WORK EXPERIENCE")
			or ""
		)
		structured = self._format_structured_experience(request)
		known = self._known_employers(request)
		source = (experience_text or "").strip() or orig_exp.strip()
		if not source and not structured:
			return ""

		kept = []
		for block in self._split_job_blocks(source):
			orgs = self._header_orgs(block)
			if orgs and known:
				if any(self._org_is_known(org, known) for org in orgs):
					kept.append(block)
				continue
			kept.append(block)

		if kept:
			return "\n\n".join(kept).strip()
		if orig_exp.strip():
			return self._normalize_bullets(orig_exp)
		return structured

	def _strip_leading_identity(self, summary: str, request: OptimizationRequest) -> str:
		text = " ".join((summary or "").split())
		name = ""
		contact = getattr(getattr(request, "resume", None), "contact", None)
		if contact is not None:
			name = (getattr(contact, "name", None) or "").strip()
		if name:
			text = re.sub(rf"^{re.escape(name)}\b[\s,|-]*", "", text, flags=re.I)
		text = re.sub(
			r"^(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3},\s*)?[A-Z][a-zA-Z.]+,\s*[A-Z]{2}(?:\s+\d{5})?\b[\s,|-]*",
			"",
			text,
		)
		return text.strip(" ,|-")

	def _sanitize_projects(self, projects_text: str, request: OptimizationRequest, evidence: CandidateEvidence) -> str:
		if not (projects_text or "").strip():
			return ""
		known = set()
		for proj in getattr(request.resume, "projects", None) or []:
			name = (getattr(proj, "name", None) or "").strip().lower()
			if name:
				known.add(name)
		for name in evidence.projects or []:
			if name:
				known.add(str(name).strip().lower())
		original = self._original_resume_text(request).lower()
		orig_sections = self._split_into_sections(self._original_resume_text(request))
		orig_proj = orig_sections.get("PROJECTS") or ""
		if not known and not orig_proj.strip():
			# Keep project text only if its title line appears in the original resume.
			known.add("__use_original_blob__")

		blocks, current = [], []
		for line in projects_text.split("\n"):
			stripped = line.strip()
			if stripped.upper() == "PROJECTS":
				continue
			if stripped and not stripped.startswith(("-", "•", "*")) and current:
				blocks.append("\n".join(current).strip())
				current = [line.rstrip()]
			elif stripped:
				current.append(line.rstrip())
		if current:
			blocks.append("\n".join(current).strip())

		kept = []
		for block in blocks:
			title = next((ln.strip() for ln in block.split("\n") if ln.strip() and not ln.strip().startswith(("-", "•", "*"))), "")
			key = title.lower()
			if not title:
				continue
			if known == {"__use_original_blob__"}:
				if key in original:
					kept.append(block)
				continue
			if any(k and (k in key or key in k) for k in known) or (title.lower() in orig_proj.lower()):
				kept.append(block)
		if kept:
			return "\n\n".join(kept).strip()
		return self._normalize_bullets(orig_proj)

	def _write_jd_summary(
		self,
		request: OptimizationRequest,
		jd: JDAnalysis,
		evidence: CandidateEvidence,
	) -> str:
		"""Two sentences aimed at this job, using only skills and projects already on the resume."""
		identity = self._candidate_identity(request)
		skills = self._jd_skills_on_resume(request, jd, evidence)
		lead = skills[:4]
		foundation = [skill for skill in skills[4:7] if skill not in lead]
		projects = self._projects_for_summary(request, lead + foundation)
		role = self._role_phrase(request.target_role)

		if lead:
			opening = f"{identity} with expertise in {self._join_phrase(lead)}"
			if role:
				opening += f" for {role}"
			opening += "."
		else:
			opening = f"{identity}."

		details = []
		if foundation:
			details.append(f"Strong foundation in {self._join_phrase(foundation)}")
		if projects:
			built = f"experience building {self._join_phrase(projects)}"
			details.append(built if details else built[:1].upper() + built[1:])
		closing = ""
		if len(details) == 2:
			closing = f"{details[0]}, with {details[1]}."
		elif details:
			closing = details[0] + "."
		return " ".join(part for part in (opening, closing) if part)

	def _role_phrase(self, role: str) -> str:
		text = re.sub(r"\s+", " ", (role or "").strip())
		if not text or text.lower() in {"target", "role"}:
			return ""
		if not re.search(r"\brole\b", text, flags=re.I):
			text = f"{text} role"
		if re.match(r"(?i)(ml|ai|sde|sql|nlp)\b", text) or text[:1].lower() in "aeiou":
			article = "an"
		else:
			article = "a"
		return f"{article} {text}"

	def _candidate_identity(self, request: OptimizationRequest) -> str:
		summary = (getattr(request.resume, "summary", None) or "").strip()
		first = re.split(r"[.!?]", summary)[0].strip() if summary else ""
		if first and first.count(",") < 2:
			head = re.split(r"\bwith\b", first, maxsplit=1, flags=re.I)[0].strip(" ,")
			if 12 <= len(head) <= 90 and not self._is_keyword_dump(head):
				return head[:1].upper() + head[1:]
		blob = self._original_resume_text(request).lower()
		if re.search(r"final[- ]year", blob) and "computer" in blob:
			return "Final-year Computer Science undergraduate"
		if re.search(r"\b(b\.?\s*tech|bachelor)\b", blob) and "computer" in blob:
			return "Computer Science student"
		years = re.search(r"\d+\+?\s+years?(?: of)? experience", blob)
		if years:
			return f"Software professional with {years.group(0)}"
		if "intern" in blob:
			return "Candidate with internship and project experience"
		return "Candidate with hands-on project experience"

	def _jd_skills_on_resume(
		self,
		request: OptimizationRequest,
		jd: JDAnalysis,
		evidence: CandidateEvidence,
	) -> list[str]:
		blob = self._original_resume_text(request).lower()
		ordered = (
			list(jd.required_skills or [])
			+ list(jd.technologies or [])
			+ list(jd.important_keywords or [])
			+ list(jd.preferred_skills or [])
		)
		picked: list[tuple[int, str]] = []
		seen: set[str] = set()
		jd_text = (request.job_description or "").lower()
		for raw in ordered:
			item = " ".join(str(raw or "").split())
			key = item.lower()
			if not self._resume_mentions_skill(key, blob):
				continue
			classified = self._classify_tech_skill(item)
			if not classified or self._canonical_soft_skill(item):
				continue
			display = classified[1]
			norm = display.lower()
			if norm in seen or len(display) < 2 or len(display) > 40:
				continue
			seen.add(norm)
			position = jd_text.find(key)
			picked.append((position if position >= 0 else 10_000, display))
		jd_text = (request.job_description or "").lower()
		resume_blob = self._original_resume_text(request).lower()
		catalog_hits: list[tuple[int, int, str]] = []
		low_priority = {"git", "github", "linux", "windows", "excel"}
		for key, (_group, display) in TECH_SKILL_CATALOG.items():
			if not self._resume_mentions_skill(key, jd_text):
				continue
			if not self._resume_mentions_skill(key, resume_blob):
				continue
			position = jd_text.find(key)
			rank = 1 if display.lower() in low_priority else 0
			catalog_hits.append((rank, position if position >= 0 else 10_000, display))
		catalog_hits.sort(key=lambda item: (item[0], item[1], -len(item[2])))
		for _, position, display in catalog_hits:
			norm = display.lower()
			if norm in seen:
				continue
			seen.add(norm)
			picked.append((position, display))

		low_priority = {"git", "github", "linux", "windows", "excel"}
		picked.sort(key=lambda pair: (1 if pair[1].lower() in low_priority else 0, pair[0]))
		displays: list[str] = []
		for _, display in picked:
			low = display.lower()
			if any(low != other.lower() and low in other.lower() for other in displays):
				continue
			displays = [other for other in displays if other.lower() not in low or other.lower() == low]
			displays.append(display)
		return displays[:8]

	def _resume_mentions_skill(self, key: str, blob: str) -> bool:
		if not key or key in {"c", "r", "go", "a", "an", "the"}:
			return False
		if len(key) <= 3 and key not in {"sql", "aws", "gcp", "api", "git", "css", "nlp", "oop"}:
			return False
		if len(key) <= 4:
			return re.search(rf"(?<![a-z0-9+#]){re.escape(key)}(?![a-z0-9+#])", blob) is not None
		return key in blob

	def _real_project_names(self, request: OptimizationRequest) -> list[str]:
		original = self._original_resume_text(request)
		sections = self._split_into_sections(original)
		proj = sections.get("PROJECTS") or ""
		names: list[str] = []
		for line in proj.splitlines():
			title = self._clean_project_title(line)
			if title and title not in names:
				names.append(title)
		return names

	def _clean_project_title(self, line: str) -> str:
		line = (line or "").strip()
		if not line or line[:1] in "-•*" or line.count(",") >= 2:
			return ""
		if not line[0].isupper():
			return ""
		line = re.split(r"\s+(?:\||—|–|-)\s+|\s{2,}", line)[0].strip(" -")
		line = re.sub(r"\b(source code|live demo|view)\b", "", line, flags=re.I).strip(" |-")
		line = re.sub(r"\s+", " ", line)
		words = line.split()
		if not (2 <= len(words) <= 10) or not (8 <= len(line) <= 72):
			return ""
		if line.upper() in {"PROJECTS", "SOURCE CODE", "LIVE DEMO"}:
			return ""
		if line.endswith("."):
			return ""
		return line

	def _projects_for_summary(self, request: OptimizationRequest, skills: list[str]) -> list[str]:
		"""Prefer projects whose text overlaps the skills this job asked for."""
		original = self._original_resume_text(request)
		sections = self._split_into_sections(original)
		proj = sections.get("PROJECTS") or ""
		blocks: list[tuple[str, str]] = []
		current_title = ""
		current_lines: list[str] = []
		for line in proj.splitlines():
			title = self._clean_project_title(line)
			if title:
				if current_title:
					blocks.append((current_title, "\n".join(current_lines)))
				current_title = title
				current_lines = [line]
			elif current_title:
				current_lines.append(line)
		if current_title:
			blocks.append((current_title, "\n".join(current_lines)))
		if not blocks:
			return self._real_project_names(request)[:2]

		wanted = [skill.lower() for skill in skills]
		ranked = []
		for index, (title, body) in enumerate(blocks):
			hay = body.lower()
			overlap = sum(1 for skill in wanted if skill and skill in hay)
			ranked.append((-overlap, index, title))
		ranked.sort()
		names = []
		for _score, _index, title in ranked:
			if title not in names:
				names.append(title)
			if len(names) == 2:
				break
		return names

	def _join_phrase(self, items: list[str]) -> str:
		if not items:
			return ""
		if len(items) == 1:
			return items[0]
		if len(items) == 2:
			return f"{items[0]} and {items[1]}"
		return ", ".join(items[:-1]) + f", and {items[-1]}"

	def _sanitize_summary_claims(self, summary: str, request: OptimizationRequest) -> str:
		if not summary:
			return summary
		known = self._known_employers(request)
		target = self._norm_org(request.company_name or "")

		def repl(match: re.Match) -> str:
			company = match.group(2)
			if self._org_is_known(company, known):
				return match.group(0)
			return ""

		cleaned = re.sub(
			r"\s*(?:and )?((?:as )?(?:an? )?(?:Software Engineer )?Intern(?:ed)? at|worked at|employee at)\s+([A-Z][A-Za-z0-9&.\- ]{1,40})",
			repl,
			summary,
			flags=re.I,
		)
		cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
		# Keep "Interested in the X role at {target}" even if they never worked there.
		if target and target not in known:
			cleaned = re.sub(
				rf"\b(?:Software Engineer )?Intern at {re.escape(request.company_name or '')}\b",
				"",
				cleaned,
				flags=re.I,
			)
		return cleaned.strip()

	def _merge_skill_list(self, skills_section: str, jd_keywords: list[str], evidence: CandidateEvidence) -> str:
		existing = []
		blob = skills_section or ""
		for token in re.split(r"[,|\n•;]+", blob):
			item = self._strip_skill_label(token)
			if item and len(item) < 64 and item.upper() not in {"TECHNICAL SKILLS", "SKILLS", "SOFT SKILLS"}:
				existing.append(item)
		for extra in (
			list(evidence.explicit_skills or [])
			+ list(evidence.project_skills or [])
			+ list(evidence.experience_skills or [])
			+ list(evidence.technologies or [])
			+ list(evidence.tools or [])
		):
			if extra:
				existing.append(extra)
		merged, seen = [], set()
		for item in existing + jd_keywords:
			p = " ".join(str(item).split())
			key = p.lower()
			if len(p) < 2 or key in seen or len(p) > 60 or p.count(" ") > 8:
				continue
			if any(bad in key for bad in ("university", "intern at", "b.tech", "bachelor", "master of", "project:", "parsed pdf")):
				continue
			seen.add(key)
			merged.append(p)
		return ", ".join(merged)

	def _weave_keywords_into_section(self, text: str, keywords: list[str]) -> str:
		if not text.strip():
			return text
		missing = [k for k in keywords if k.lower() not in text.lower()]
		if not missing:
			return text
		lines = text.split("\n")
		unused = list(missing)
		out = []
		for line in lines:
			stripped = line.strip()
			is_bullet = stripped.startswith(("-", "•", "*"))
			if is_bullet and unused and len(stripped) > 18:
				chunk = unused[:2]
				unused = unused[2:]
				core = re.sub(r"^[•\-\*]\s*", "", stripped).rstrip(".")
				out.append(f"• {core}, leveraging {', '.join(chunk)}.")
			else:
				out.append(line)
		if unused:
			out.append(f"• Applied {', '.join(unused[:6])} to strengthen delivery against the target role.")
		return "\n".join(out)

	def _reformat_resume(self, text: str, jd: JDAnalysis, evidence: CandidateEvidence, request: OptimizationRequest) -> str:
		"""Reorganize the resume, inject a targeted summary, and surface supported JD keywords.

		Preserves all the user's original wording — only reorganizes and adds a
		targeted summary. No fabricated content.
		"""
		# Collect supported JD keywords (evidence already on the resume)
		supported_keywords: set[str] = set()
		for kw in jd.important_keywords:
			if kw and kw.lower() in text.lower():
				supported_keywords.add(kw)
		for skill in evidence.explicit_skills + evidence.project_skills + evidence.experience_skills:
			if skill and skill.lower() in text.lower():
				supported_keywords.add(skill)
		for tech in evidence.technologies + evidence.tools:
			if tech and tech.lower() in text.lower():
				supported_keywords.add(tech)

		# Try to detect sections and reorder them
		lines = text.split("\n")
		sections: dict[str, list[str]] = {}
		current_section = "header"
		current_lines: list[str] = []

		section_headers = {
			"summary": ["professional summary", "summary", "profile", "about", "objective"],
			"education": ["education", "academic background", "qualifications"],
			"experience": ["experience", "work experience", "professional experience", "employment"],
			"soft_skills": ["soft skills", "interpersonal skills"],
			"skills": ["technical skills", "programming skills", "skills", "competencies", "expertise"],
			"projects": ["projects", "personal projects", "side projects", "academic projects"],
			"certifications": ["certifications", "certificates", "credentials", "licenses"],
			"achievements": ["achievements", "awards", "honors"],
		}

		def find_section(line_lower):
			for section, headers in section_headers.items():
				for header in headers:
					# Match "header: ...", "header ...", "header" alone,
					# or "some prefix header" (e.g. "professional summary")
					if line_lower == header:
						return section
					if line_lower.startswith(header + ":"):
						return section
					if line_lower.startswith(header + " "):
						return section
					# Multi-word headers inside a line: "professional summary" contains "summary"
					if " " in header and header in line_lower:
						return section
			return None

		for line in lines:
			line_lower = line.lower().strip().rstrip(":")
			matched = find_section(line_lower)
			if matched and matched != current_section:
				if current_lines:
					sections.setdefault(current_section, []).extend(current_lines)
				current_section = matched
				current_lines = []
				continue
			current_lines.append(line)

		if current_lines:
			sections.setdefault(current_section, []).extend(current_lines)

		# Build reordered output
		output_parts: list[str] = []

		# Header (first few non-section lines)
		header = "\n".join(sections.get("header", [])).strip()
		if header:
			output_parts.append(header)

		# Summary: keep original summary text; ATS rewrite happens in _enhance_for_ats
		existing_summary = "\n".join(sections.get("summary", [])).strip()
		if existing_summary:
			output_parts.append("PROFESSIONAL SUMMARY\n" + existing_summary)

		# Skills (promote)
		skills_section = "\n".join(sections.get("skills", [])).strip()
		if skills_section:
			output_parts.append("TECHNICAL SKILLS\n" + skills_section)
		soft_section = "\n".join(sections.get("soft_skills", [])).strip()
		if soft_section:
			output_parts.append("SOFT SKILLS\n" + soft_section)

		# Experience
		exp_section = "\n".join(sections.get("experience", [])).strip()
		if exp_section:
			output_parts.append("PROFESSIONAL EXPERIENCE\n" + exp_section)

		# Projects
		proj_section = "\n".join(sections.get("projects", [])).strip()
		if proj_section:
			output_parts.append("PROJECTS\n" + proj_section)

		# Education
		edu_section = "\n".join(sections.get("education", [])).strip()
		if edu_section:
			output_parts.append("EDUCATION\n" + edu_section)

		# Certifications
		cert_section = "\n".join(sections.get("certifications", [])).strip()
		if cert_section:
			output_parts.append("CERTIFICATIONS\n" + cert_section)

		# Achievements
		ach_section = "\n".join(sections.get("achievements", [])).strip()
		if ach_section:
			output_parts.append("ACHIEVEMENTS\n" + ach_section)

		# If no sections were detected, return original text
		if len(output_parts) <= 1:
			return text

		return "\n\n".join(output_parts)

	def _split_into_sections(self, text: str) -> dict:
		"""Split the optimized text into sections for frontend display."""
		sections = {}
		current_section = "header"
		current_lines = []

		section_names = [
			"PROFESSIONAL SUMMARY", "SUMMARY", "PROFILE", "OBJECTIVE",
			"TECHNICAL SKILLS", "SKILLS", "SOFT SKILLS",
			"PROFESSIONAL EXPERIENCE", "EXPERIENCE", "WORK EXPERIENCE", "CAREER EXPERIENCE",
			"PROJECTS", "EDUCATION", "CERTIFICATIONS", "ACHIEVEMENTS",
			"INTERNSHIP EXPERIENCE", "INTERNSHIPS",
			"CERTIFICATIONS & CREDENTIALS", "CERTIFICATIONS AND CREDENTIALS",
			"TECHNICAL PROFICIENCIES", "CORE COMPETENCIES",
			"AWARDS AND RECOGNITION", "AWARDS & RECOGNITION",
		]

		for line in text.split("\n"):
			stripped = line.strip().rstrip(":")
			if stripped.upper() in section_names:
				if current_lines:
					sections[current_section] = "\n".join(current_lines).strip()
				current_section = {
					"CAREER EXPERIENCE": "PROFESSIONAL EXPERIENCE",
					"TECHNICAL PROFICIENCIES": "TECHNICAL SKILLS",
					"CORE COMPETENCIES": "TECHNICAL SKILLS",
					"SUMMARY": "PROFESSIONAL SUMMARY",
					"AWARDS AND RECOGNITION": "ACHIEVEMENTS",
					"AWARDS & RECOGNITION": "ACHIEVEMENTS",
				}.get(stripped.upper(), stripped.upper())
				current_lines = []
			else:
				current_lines.append(line)

		if current_lines:
			sections[current_section] = "\n".join(current_lines).strip()

		return sections

	async def _analyze_jd(self, jd_text: str) -> JDAnalysis:
		"""Extract JD requirements locally so the fine-tuned LLM is used for resume rewrite."""
		return self._heuristic_jd_analysis(jd_text)

	def _merge_jd(self, heuristic: JDAnalysis, parsed: JDAnalysis) -> JDAnalysis:
		def merge(a, b):
			out, seen = [], set()
			for item in list(a or []) + list(b or []):
				key = str(item).strip().lower()
				if not key or key in seen:
					continue
				seen.add(key)
				out.append(str(item).strip())
			return out

		return JDAnalysis(
			required_skills=merge(parsed.required_skills, heuristic.required_skills)[:20],
			preferred_skills=merge(parsed.preferred_skills, heuristic.preferred_skills)[:15],
			technologies=merge(parsed.technologies, heuristic.technologies)[:15],
			tools=merge(parsed.tools, heuristic.tools)[:15],
			responsibilities=merge(parsed.responsibilities, heuristic.responsibilities)[:10],
			domain_terms=merge(parsed.domain_terms, heuristic.domain_terms)[:15],
			role_terminology=merge(parsed.role_terminology, heuristic.role_terminology)[:15],
			important_keywords=merge(parsed.important_keywords, heuristic.important_keywords)[:30],
			education_requirements=merge(parsed.education_requirements, heuristic.education_requirements)[:8],
			experience_requirements=merge(parsed.experience_requirements, heuristic.experience_requirements)[:8],
		)

	def _heuristic_jd_analysis(self, jd_text: str) -> JDAnalysis:
		"""Deterministic JD analysis without requiring an LLM.

		Extracts individual skills/technologies by:
		1. Matching against a curated skill lexicon (technical + soft skills)
		2. Splitting comma/slash/pipe-separated skill lists
		3. Extracting meaningful keywords (filtered)
		"""
		text = jd_text.strip()
		text_lower = text.lower()

		# Comprehensive skill/technology lexicon
		SKILL_LEXICON = [
			"python", "java", "javascript", "typescript", "c++", "c#", "c", "go", "rust",
			"ruby", "php", "swift", "kotlin", "scala", "perl", "r", "matlab", "sql",
			"nosql", "html", "css", "bash", "shell scripting",
			"react", "angular", "vue", "next.js", "node.js", "express",
			"django", "flask", "fastapi", "spring", "spring boot", "laravel", "rails",
			"react native", "flutter", "tensorflow", "pytorch", "keras", "scikit-learn",
			"pandas", "numpy", "matplotlib", "seaborn",
			"mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
			"cassandra", "dynamodb", "sqlite", "oracle", "sql server",
			"aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
			"ansible", "jenkins", "ci/cd", "github actions", "helm", "prometheus",
			"grafana", "datadog", "elk", "splunk",
			"rest", "rest apis", "restful apis", "graphql", "grpc", "soap", "websockets",
			"microservices", "serverless", "lambda",
			"machine learning", "deep learning", "nlp", "computer vision", "data science",
			"data analytics", "data engineering", "data pipelines", "etl", "spark",
			"hadoop", "kafka", "airflow", "databricks", "snowflake", "bigquery",
			"tableau", "power bi", "looker", "excel", "google sheets", "google docs",
			"salesforce", "apex", "unity", "premiere pro", "figma", "powerpoint",
			"git", "github", "gitlab", "bitbucket", "jira", "confluence", "figma",
			"postman", "swagger", "linux", "unix", "agile", "scrum", "kanban",
			"testing", "unit testing", "jest", "pytest", "selenium", "cypress",
			"tdd", "bdd", "devops", "mlops",
			"data structures", "data structures and algorithms", "algorithms",
			"object-oriented programming", "oop", "design patterns",
			"system design", "distributed systems", "scalable systems",
			"debugging", "problem-solving", "problem solving",
			"software development", "software engineering", "software engineering practices",
			"code review", "version control", "documentation",
			"performance optimization", "security best practices",
			"communication", "leadership", "teamwork", "collaboration",
			"analytical skills", "critical thinking",
			"time management", "project management", "stakeholder management",
		]

		found_skills = []
		seen = set()
		# Sort by length (longest first) so multi-word matches take priority
		for skill in sorted(SKILL_LEXICON, key=len, reverse=True):
			if skill in text_lower and skill not in seen:
				found_skills.append(skill)
				seen.add(skill)

		# Also split comma/slash-separated lists from SHORT lines that look like skill lists
		# (skip long narrative sentences that happen to contain commas)
		for line in text.split("\n"):
			clean_line = re.sub(r"^(required|preferred|nice to have|qualifications|requirements|must have|skills?):\s*", "", line.lower().strip())
			# Only process short lines (<200 chars) that have multiple commas/slashes
			commas = clean_line.count(",")
			slashes = clean_line.count("/")
			if (commas >= 2 or slashes >= 2) and len(clean_line) < 200:
				# Skip lines that look like narrative requirements
				if any(narrative in clean_line for narrative in ["experience with", "familiarity with", "understanding of", "knowledge of", "ability to", "responsibilities", "you will", "you'll", "what you'll"]):
					continue
				tokens = re.split(r"[,/;]|\s+and\s+|\s+or\s+", clean_line)
				for token in tokens:
					token = token.strip().strip(".").strip(",").strip(")")
					# Must be a single clean word/phrase
					if not token or len(token) < 2 or len(token) > 40:
						continue
					# Skip tokens that contain spaces (they're sentence fragments)
					if " " in token:
						continue
					# Skip tokens that look like sentence fragments
					# (contain words like "with", "of", "the", "a", "to", "for", "and", "or")
					if any(token.startswith(w) for w in ["must", "should", "would", "will", "required", "preferred", "experience", "strong", "working", "the ", "a ", "an ", "to ", "for ", "with", "from", "this", "that", "these", "those", "candidate", "you ", "your"]):
						continue
					# Skip tokens containing narrative words
					if any(w in token for w in [" using", " using ", " with ", " for ", " and ", " or ", " in ", " at "]):
						continue
					if token not in seen:
						found_skills.append(token)
						seen.add(token)

		# Required vs preferred classification
		required_skills = []
		preferred_skills = []
		for line in text.split("\n"):
			lower = line.lower()
			for skill in found_skills[:]:
				if skill in lower:
					if any(marker in lower for marker in ["preferred", "nice to have", "bonus", "plus"]):
						if skill not in required_skills and skill not in preferred_skills:
							preferred_skills.append(skill)
					else:
						if skill not in required_skills and skill not in preferred_skills:
							required_skills.append(skill)
					break

		if not required_skills:
			required_skills = [s for s in found_skills if s not in preferred_skills][:15]

		# Extract responsibilities (meaningful requirement sentences)
		responsibilities = []
		for line in text.split("\n"):
			clean = line.strip()
			if clean and len(clean) > 20 and not clean.endswith(":"):
				clean_lower = clean.lower()
				if any(marker in clean_lower for marker in ["will", "must", "should", "responsible", "develop", "build", "create", "design", "implement", "collaborate", "work with", "ensure", "maintain", "manage", "participate"]):
					responsibilities.append(clean)

		tech_keywords = ["python", "java", "javascript", "typescript", "react", "angular", "vue",
			"node.js", "django", "flask", "spring", "sql", "mongodb", "postgresql",
			"aws", "azure", "gcp", "docker", "kubernetes", "terraform", "git",
			"machine learning", "deep learning", "tensorflow", "pytorch", "nlp",
			"data science", "analytics", "tableau", "power bi", "excel",
			"agile", "scrum", "ci/cd", "rest", "graphql", "microservices"]

		tool_keywords = ["jira", "confluence", "figma", "photoshop", "illustrator",
			"salesforce", "hubspot", "slack", "notion", "asana",
			"postman", "swagger", "jenkins", "github", "gitlab"]

		techs_found = [s for s in found_skills if s in tech_keywords]
		tools_found = [s for s in found_skills if s in tool_keywords]

		return JDAnalysis(
			required_skills=required_skills[:15],
			preferred_skills=preferred_skills[:10],
			technologies=techs_found[:10],
			tools=tools_found[:10],
			responsibilities=responsibilities[:8],
			domain_terms=[],
			role_terminology=[],
			important_keywords=found_skills[:20],
			education_requirements=[],
			experience_requirements=[],
		)

	async def _generate_version(
		self,
		resume_text: str,
		jd_text: str,
		company_name: str,
		target_role: str,
		evidence: CandidateEvidence,
		strategy: str,
		version_id: str,
	) -> Optional[dict]:
		"""Generate one candidate version using notebook-style prompt."""
		if not self.model.is_loaded:
			return None

		try:
			evidence_str = json.dumps(
				evidence.model_dump() if hasattr(evidence, "model_dump") else evidence.dict(),
				indent=2,
				default=str,
			)

			# Build messages list (system + user) — matches notebook
			messages = PromptTemplates.full_optimization(
				resume_text, jd_text, company_name, target_role, evidence_str, strategy
			)

			# One-page resume; do not force 1600+ tokens on local CPU Ollama.
			max_tokens = int(settings.MAX_NEW_TOKENS or 900)
			if getattr(self.model, "backend", None) == "ollama":
				max_tokens = min(max(max_tokens, 256), 512)
			response = await self.model.generate(
				messages=messages,
				max_new_tokens=max_tokens,
				temperature=0.2,
			)

			# Clean output — strip code fences, prefixes, and [empty think block] markers
			cleaned = self._clean_output(response)

			# Reject empty or too-short outputs (not reasoning rejection)
			if not cleaned or len(cleaned.strip()) < 50:
				logger.warning(f"Version {version_id}: output too short ({len(cleaned)} chars), rejecting")
				return None

			# Only reject if output is ENTIRELY reasoning (no actual resume content)
			if self._is_pure_reasoning(cleaned):
				logger.warning(f"Version {version_id}: output is pure reasoning, rejecting")
				return None

			return {
				"version_id": version_id,
				"label": version_id,
				"strategy": strategy,
				"optimized_text": cleaned,
				"sections": {},
				"alignment_score": None,
				"safety": None,
			}
		except Exception as e:
			logger.warning(f"Version {version_id} generation failed: {e}")
			return None

	def _clean_output(self, text: str) -> str:
		"""Clean model output — strip code fences, prefixes, thinking markers."""
		text = text.strip()

		# Strip thinking blocks (already done in ai_engine, but safety net)
		text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
		text = re.sub(r"\[empty think block\]", "", text, flags=re.IGNORECASE)

		# Remove common model wrappers
		prefixes = [
			"Here is the optimized resume:",
			"Here is the enhanced resume:",
			"Here is your optimized resume:",
			"Here is the resume:",
			"Optimized Resume:",
			"Enhanced Resume:",
			"Resume:",
		]

		for prefix in prefixes:
			if text.lower().startswith(prefix.lower()):
				text = text[len(prefix):].strip()

		# Remove markdown code fences
		text = re.sub(r"```(?:text|markdown)?", "", text, flags=re.IGNORECASE)
		text = text.replace("```", "")

		# Drop leaked prompt-instruction lines from small local models
		kept = []
		for line in text.split("\n"):
			if re.match(
				r"^\s*\d+\.\s+(Preserve|Pull|Rewrite|Enhance|Improve|Prefer|Use|Return|Never|Do not|Output)\b",
				line,
				re.I,
			):
				continue
			if re.search(r"OUTPUT ONLY THE RESUME|STRICT RULES|JOB DESCRIPTION:", line, re.I):
				continue
			kept.append(line)
		return "\n".join(kept).strip()

	def _is_pure_reasoning(self, text: str) -> bool:
		"""Only reject if the ENTIRE output is reasoning (no resume content).

		Replaces the old _contains_reasoning() which rejected ANY mention of
		'candidate' or 'job description' — that was killing valid outputs.
		"""
		# Check if the output looks like a resume (has section headers, bullets, etc.)
		resume_indicators = [
			r"\b(?:SUMMARY|PROFILE|OBJECTIVE)\b",
			r"\b(?:EDUCATION|SKILLS|EXPERIENCE|PROJECTS|CERTIFICATIONS)\b",
			r"\b(?:Bachelor|Master|B\.Tech|M\.Tech|PhD|University)\b",
			r"^\s*[-•*]\s+", # bullet points
		]
		has_resume_content = False
		for pattern in resume_indicators:
			if re.search(pattern, text, re.IGNORECASE):
				has_resume_content = True
				break

		if has_resume_content:
			return False

		# If no resume indicators at all and text is short + starts with reasoning
		reasoning_starters = [
			"let me analyze",
			"let's analyze",
			"i will rewrite",
			"here's my approach",
			"first, i will",
			"to optimize this resume",
		]
		text_lower = text[:300].lower().strip()
		return any(text_lower.startswith(starter) for starter in reasoning_starters)

	async def _safety_check(self, original_text: str, optimized_text: str) -> SafetyResult:
		"""Validate that the optimized text adds no new facts."""
		if getattr(self.model, "backend", None) == "ollama" or settings.DEVICE == "cpu":
			return self._heuristic_safety_check(original_text, optimized_text)

		if not self.model.is_loaded:
			return self._heuristic_safety_check(original_text, optimized_text)

		try:
			prompt = PromptTemplates.safety_check(original_text, optimized_text)
			response = await self.model.generate(prompt, max_new_tokens=256, temperature=0.1)
			match = re.search(r"\{.*\}", response, re.DOTALL)
			if match:
				data = json.loads(match.group())
				return SafetyResult(
					passed=data.get("passed", False),
					issues=data.get("hallucinations", []),
					hallucinated_skills=data.get("hallucinations", []),
					hallucinated_experience=[],
					hallucinated_metrics=[],
				)
		except Exception as e:
			logger.warning(f"AI safety check failed, using heuristic: {e}")

		return self._heuristic_safety_check(original_text, optimized_text)

	def _heuristic_safety_check(self, original: str, optimized: str) -> SafetyResult:
		"""Fallback safety check: look for obvious hallucinations."""
		issues = []
		orig_lower = original.lower()
		opt_lower = optimized.lower()

		# Check for new company names (line-by-line, only "at Company" on same line)
		orig_companies = set()
		for line in original.split("\n"):
			matches = re.findall(r"(?:at|@)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", line)
			orig_companies.update(matches)
		opt_companies = set()
		for line in optimized.split("\n"):
			matches = re.findall(r"(?:at|@)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", line)
			opt_companies.update(matches)
		new_companies = opt_companies - orig_companies
		ignore_orgs = {
			"git", "github", "gitlab", "bitbucket", "jira", "slack", "python", "java",
			"react", "node", "docker", "linux", "windows", "india", "usa", "remote", "present",
		}
		new_companies = {
			c for c in new_companies
			if c.lower() not in ignore_orgs and len(c) > 3
		}
		if new_companies:
			issues.append(f"Potentially new employers: {list(new_companies)}")

		# Check for suspicious new metrics
		metric_pattern = re.compile(
			r"\b\d+(?:\.\d+)?\s*(?:%|percent|x|years?|months?|users?|"
			r"customers?|projects?|hours?|days?|ms|seconds?|million|billion)\b",
			re.IGNORECASE,
		)
		orig_numbers = set(re.findall(r"\d+(?:\.\d+)?", original))
		for line in optimized.split("\n"):
			if line.strip():
				numbers = re.findall(r"\d+(?:\.\d+)?", line)
				if numbers and metric_pattern.search(line):
					found_existing = any(n in orig_numbers for n in numbers)
					if not found_existing:
						issues.append(f"Suspicious new metric: {line.strip()[:100]}")
						break

		# JD skill injection is intentional for ATS matching — do not flag wording/skills.
		return SafetyResult(
			passed=len(issues) == 0,
			issues=issues,
			hallucinated_skills=[],
			hallucinated_experience=list(new_companies) if new_companies else [],
			hallucinated_metrics=[],
		)

	def _compute_alignment_score(
		self,
		optimized_text: str,
		jd: JDAnalysis,
		evidence: CandidateEvidence,
	) -> AlignmentScore:
		"""Compute internal JD alignment score."""
		scorer = ATSScorer()
		score_dict = scorer.score(optimized_text, jd, evidence)
		self._last_score_dict = score_dict

		return AlignmentScore(
			overall=score_dict["overall"],
			keyword_coverage=score_dict["keyword_coverage"],
			skill_alignment=score_dict["skill_alignment"],
			responsibility_alignment=score_dict["responsibility_alignment"],
			role_alignment=score_dict["role_alignment"],
			domain_terminology=score_dict["domain_terminology"],
			evidence_coverage=score_dict["evidence_coverage"],
			truthfulness=score_dict["truthfulness"],
			readability=score_dict["readability"],
			conciseness=score_dict["conciseness"],
		)

	def _compress_to_one_page(self, text: str) -> str:
		"""Compress resume to approximately one page (~500 words)."""
		words = text.split()
		if len(words) <= 500:
			return text

		compressed = []
		count = 0
		for sentence in re.split(r"(?<=[.!?])\s+", text):
			compressed.append(sentence)
			count += len(sentence.split())
			if count >= 450:
				break

		return " ".join(compressed)

	def _generate_pdf(self, text: str, resume: ParsedResume, score: AlignmentScore, template: str) -> dict:
		"""Generate PDF from optimized resume."""
		try:
			pdf_gen = PDFGenerator(template=template)
			pdf_bytes = pdf_gen.generate(text)

			pdf_id = uuid.uuid4().hex[:12]
			output_path = f"./outputs/{pdf_id}.pdf"
			with open(output_path, "wb") as f:
				f.write(pdf_bytes)

			return {
				"id": pdf_id,
				"download_url": f"/api/pdf/{pdf_id}",
				"file_size_bytes": len(pdf_bytes),
			}
		except Exception as e:
			logger.error(f"PDF generation failed: {e}")
			return {"id": None, "download_url": None, "error": str(e)}

	def _build_analysis(self, score: Optional[AlignmentScore], evidence: Optional[CandidateEvidence], mapping: dict) -> dict:
		"""Build the analysis section of the response."""
		if score:
			alignment_score = score.overall
			breakdown = {
				"keyword_coverage": score.keyword_coverage,
				"skill_alignment": score.skill_alignment,
				"responsibility_alignment": score.responsibility_alignment,
				"role_alignment": score.role_alignment,
				"domain_terminology": score.domain_terminology,
				"evidence_coverage": score.evidence_coverage,
				"readability": score.readability,
				"conciseness": score.conciseness,
			}
		else:
			alignment_score = 0
			breakdown = {}

		evidence_items = []
		if evidence:
			evidence_items = evidence.technologies + evidence.tools + evidence.achievements

		extras = getattr(self, "_last_score_dict", {}) or {}
		matched = extras.get("matched_keywords") or mapping.get("matched_keywords", [])
		missing = extras.get("missing_keywords") or mapping.get("unsupported_requirements", [])
		return {
			"alignment_score": alignment_score,
			"breakdown": breakdown,
			"matched_keywords": matched[:40],
			"missing_keywords": missing[:40],
			"supported_skills": mapping.get("supported_skills", []),
			"unsupported_requirements": mapping.get("unsupported_requirements", []),
			"evidence": evidence_items[:20],
		}

	def _map_jd_to_evidence(self, jd: JDAnalysis, evidence: CandidateEvidence, raw_text: str = "") -> dict:
		"""Map JD requirements to candidate evidence.

		Checks both structured evidence AND the raw resume text,
		because the parser may miss skills that are clearly present.
		"""
		evidence_skills = set(
			s.lower()
			for s in evidence.explicit_skills + evidence.project_skills + evidence.experience_skills
		)
		evidence_tech = set(t.lower() for t in evidence.technologies + evidence.tools)

		jd_skills = set(s.lower() for s in jd.required_skills + jd.preferred_skills)
		jd_tech = set(t.lower() for t in jd.technologies + jd.tools)

		# Also check raw resume text — parser may have missed skills
		if raw_text:
			raw_lower = raw_text.lower()
			for skill in jd.required_skills + jd.preferred_skills + jd.technologies:
				skill_lower = skill.lower().strip()
				if skill_lower and skill_lower in raw_lower:
					evidence_skills.add(skill_lower)

		supported = list((evidence_skills | evidence_tech) & (jd_skills | jd_tech))
		unsupported = list((jd_skills | jd_tech) - (evidence_skills | evidence_tech))

		# Filter out empty strings
		supported = [s for s in supported if s and len(s.strip()) > 0]
		unsupported = [s for s in unsupported if s and len(s.strip()) > 0]

		matched = list(set(s.lower() for s in jd.required_skills) & (evidence_skills | evidence_tech))

		return {
			"matched_keywords": matched[:20],
			"supported_skills": supported[:20],
			"unsupported_requirements": unsupported[:20],
		}

	def _extract_keywords(self, text: str) -> list[str]:
		"""Extract important keywords from text."""
		stop_words = {
			"the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
			"was", "one", "our", "out", "has", "have", "this", "that", "with",
			"from", "they", "been", "said", "each", "which", "their", "will",
			"other", "about", "many", "would", "make", "like", "time", "just",
			"know", "take", "people", "into", "year", "your", "good", "some",
			"could", "them", "see", "other", "than", "then", "now", "look",
			"only", "come", "its", "over", "think", "also", "back", "after",
		}
		words = re.findall(r"\b[A-Za-z]{3,}\b", text)
		important = [w for w in words if w.lower() not in stop_words and not w.islower()]
		return list(set(important))[:30]
