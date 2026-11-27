"""
Resume Parser: extracts structured data from PDF, DOCX, TXT files.
Also provides normalization and evidence extraction per the spec.
"""

import re
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document as DocxDocument

from app.models.schemas import (
	CandidateEvidence,
	ContactInfo,
	Education,
	ParsedResume,
	Project,
	Skill,
	WorkExperience,
)


class ResumeParser:
	"""Parse, normalize, and extract evidence from resumes."""

	SECTION_HEADERS = {
		"summary": ["professional summary", "summary", "profile", "about me", "objective"],
		"experience": ["experience", "work experience", "professional experience", "employment history", "work history"],
		"education": ["education", "academic background", "qualifications"],
		"skills": ["skills", "technical skills", "competencies", "expertise"],
		"soft_skills": ["soft skills", "interpersonal skills"],
		"projects": ["projects", "personal projects", "side projects"],
		"certifications": ["certifications", "certificates", "credentials", "licenses"],
	}

	def parse_file(self, file_path: str, file_type: str) -> str:
		"""Read a file and return its text content."""
		path = Path(file_path)
		if not path.exists():
			raise FileNotFoundError(f"File not found: {file_path}")

		ft = file_type.lower()
		if ft == "pdf":
			return self._parse_pdf(path)
		elif ft == "docx":
			return self._parse_docx(path)
		elif ft == "txt":
			return self._parse_txt(path)
		else:
			raise ValueError(f"Unsupported file type: {file_type}")

	def _parse_pdf(self, path: Path) -> str:
		parts = []
		with pdfplumber.open(path) as pdf:
			for page in pdf.pages:
				# Default x_tolerance glues nearby words ("Engineeredafull-stack").
				text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
				if text.strip():
					parts.append(text)
		return restore_resume_spacing("\n\n".join(parts))

	def _parse_docx(self, path: Path) -> str:
		doc = DocxDocument(path)
		return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

	def _parse_txt(self, path: Path) -> str:
		return path.read_text(encoding="utf-8", errors="replace")

	def parse(self, text: str) -> dict:
		"""Parse raw text into structured dict (basic extraction)."""
		lines = [l.strip() for l in text.split("\n") if l.strip()]
		sections = self._detect_sections(lines)

		return {
			"contact": self._extract_contact(text, lines),
			"summary": sections.get("summary", ""),
			"experience": self._parse_experiences(sections.get("experience", "")),
			"education": self._parse_education(sections.get("education", "")),
			"skills": self._parse_skills(sections.get("skills", "")),
			"projects": self._parse_projects(sections.get("projects", "")),
			"certifications": self._parse_certifications(sections.get("certifications", "")),
			"raw_text": text,
			"word_count": len(text.split()),
			"page_count": max(1, len(text) // 3000),
		}

	def normalize(self, parsed: ParsedResume) -> ParsedResume:
		"""Normalize the parsed resume."""
		normalized = parsed.model_copy() if hasattr(parsed, "model_copy") else parsed

		cleaned_exp = []
		seen = set()
		for exp in normalized.experience:
			key = (exp.title.lower(), exp.company.lower())
			if key not in seen:
				seen.add(key)
				exp.description = [self._clean_bullet(b) for b in exp.description]
				exp.achievements = [self._clean_bullet(a) for a in exp.achievements]
				cleaned_exp.append(exp)
		normalized.experience = cleaned_exp

		seen_skills = set()
		cleaned_skills = []
		for skill in normalized.skills:
			name = skill.name.strip().lower()
			if name not in seen_skills:
				seen_skills.add(name)
				skill.name = skill.name.strip()
				cleaned_skills.append(skill)
		normalized.skills = cleaned_skills

		return normalized

	def _clean_bullet(self, text: str) -> str:
		text = text.strip()
		text = re.sub(r"^[-•*]\s*", "", text)
		text = re.sub(r"\s+", " ", text)
		return text

	def extract_evidence(self, resume_text: str) -> CandidateEvidence:
		"""Extract structured evidence from the ORIGINAL resume text."""
		text_lower = resume_text.lower()

		explicit_skills = self._extract_skills_from_text(resume_text)
		project_skills = self._extract_project_skills(resume_text)
		experience_skills = self._extract_experience_skills(resume_text)
		technologies = self._extract_technologies(resume_text)
		tools = self._extract_tools(resume_text)
		employers = self._extract_employers(resume_text)
		titles = self._extract_titles(resume_text)
		education = self._extract_education_entries(resume_text)
		certifications = self._extract_certifications(resume_text)
		achievements = self._extract_achievements(resume_text)
		metrics = self._extract_metrics(resume_text)
		projects = self._extract_project_names(resume_text)

		return CandidateEvidence(
			explicit_skills=explicit_skills,
			project_skills=project_skills,
			experience_skills=experience_skills,
			technologies=technologies,
			tools=tools,
			projects=projects,
			employers=employers,
			titles=titles,
			education=education,
			certifications=certifications,
			achievements=achievements,
			metrics=metrics,
		)

	def _detect_sections(self, lines):
		sections = {}
		current = "header"
		current_lines = []

		for line in lines:
			normalized = line.lower().strip()
			matched = None

			for section_name, headers in self.SECTION_HEADERS.items():
				for header in headers:
					if normalized == header or normalized.startswith(header + " ") or normalized.startswith(header + ":"):
						matched = section_name
						break
				if matched:
					break

			if matched != current:
				if current not in sections:
					sections[current] = []
				sections[current].extend(current_lines)
				current = matched
				current_lines = [line]
			elif matched:
				current = matched
				current_lines = [line]
			else:
				current_lines.append(line)

		if current not in sections:
			sections[current] = []
		sections[current].extend(current_lines)

		return {k: "\n".join(v) for k, v in sections.items()}

	def _extract_contact(self, text, lines):
		email = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
		phone = re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
		linkedin = re.search(r"linkedin\.com/in/[\w\-]+", text, re.IGNORECASE)
		github = re.search(r"github\.com/[\w\-]+", text, re.IGNORECASE)

		name = ""
		for line in lines[:5]:
			if "@" not in line and not re.search(r"\d{3}", line) and len(line) > 1:
				name = line
				break

		return {
			"name": name,
			"email": email.group() if email else None,
			"phone": phone.group() if phone else None,
			"linkedin": f"https://{linkedin.group()}" if linkedin else None,
			"github": f"https://{github.group()}" if github else None,
			"location": None,
			"portfolio": None,
		}

	def _parse_experiences(self, text):
		if not text.strip():
			return []

		experiences = []
		lines = text.split("\n")
		current = {}
		bullets = []

		date_pattern = re.compile(
			r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
			r"|(?:19|20)\d{2})\s*[-–—]\s*"
			r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
			r"|(?:19|20)\d{2}|Present|Current)",
			re.IGNORECASE,
		)

		for line in lines:
			if date_pattern.search(line):
				if current:
					current["description"] = bullets
					experiences.append(current)
				dates = date_pattern.search(line).groups()
				current = {
					"title": "",
					"company": "",
					"start_date": dates[0],
					"end_date": dates[1],
					"description": [],
					"achievements": [],
				}
				bullets = []
			elif line.startswith("- ") or line.startswith("* ") or line.startswith("•"):
				bullets.append(line[2:].strip())
			elif current and not line[0].isdigit():
				bullets.append(line.strip())

		if current:
			current["description"] = bullets
			experiences.append(current)

		return experiences if experiences else [{"title": "", "company": "", "start_date": "", "end_date": None, "description": [], "achievements": []}]

	def _parse_education(self, text):
		if not text.strip():
			return []
		return [{"institution": "", "degree": "", "field_of_study": "", "start_date": "", "end_date": None}]

	def _parse_skills(self, text):
		if not text.strip():
			return []
		raw = re.split(r"[,;|\n•*]|\s+-\s+", text)
		skills = []
		seen = set()
		for s in raw:
			s = s.strip()
			if s and len(s) > 1 and s.lower() not in seen:
				seen.add(s.lower())
				skills.append(Skill(name=s, category="Technical"))
		return skills

	def _parse_projects(self, text):
		"""Parse individual projects from a projects section."""
		if not text.strip():
			return []

		projects = []
		lines = [l.strip() for l in text.split("\n") if l.strip()]

		current = None
		current_bullets = []
		techs = []

		for line in lines:
			# Detect a new project header: "Project Name | tech1, tech2" or "Project Name — tech1, tech2"
			# or just a standalone title line
			tech_separator = None
			for sep in [" | ", " — ", " - ", " • "]:
				if sep in line and not line.startswith(("-", "•", "*")):
					tech_separator = sep
					break

			if tech_separator and not line.startswith(("-", "•", "*")):
				# Save previous project
				if current:
					projects.append(Project(
						name=current,
						description=" ".join(current_bullets),
						technologies=techs,
						highlights=current_bullets,
					))
				parts = line.split(tech_separator, 1)
				current = parts[0].strip()
				techs = [t.strip() for t in parts[1].split(",") if t.strip()]
				current_bullets = []
			elif line.startswith(("-", "•", "*")):
				bullet = re.sub(r"^[-•*]\s*", "", line).strip()
				current_bullets.append(bullet)
			elif current is None:
				# First line that isn't a bullet = project name
				current = line
			else:
				current_bullets.append(line)

		# Save last project
		if current:
			projects.append(Project(
				name=current,
				description=" ".join(current_bullets),
				technologies=techs,
				highlights=current_bullets,
			))

		return projects

	def _parse_certifications(self, text):
		"""Parse certifications from a certifications section."""
		if not text.strip():
			return []

		certs = []
		lines = [l.strip() for l in text.split("\n") if l.strip()]

		for line in lines:
			# Skip common non-cert lines
			if any(skip in line.lower() for skip in ["certifications", "certificates", "credentials", "licenses"]):
				continue
			if line.startswith(("-", "•", "*")):
				line = re.sub(r"^[-•*]\s*", "", line).strip()

			# Parse "Certification Name — Issuer" or "Certification Name"
			issuer = None
			name = line
			for sep in [" — ", " - ", " | "]:
				if sep in line:
					parts = line.split(sep, 1)
					name = parts[0].strip()
					issuer = parts[1].strip() if len(parts) > 1 else None
					break

			if name:
				certs.append(Certification(name=name, issuer=issuer))

		return certs

	def _extract_skills_from_text(self, text):
		skills = []
		skill_section = ""
		lines = text.split("\n")
		in_skills = False
		for line in lines:
			lower = line.lower().strip().rstrip(":")
			if lower in ["skills", "technical skills", "competencies", "expertise"]:
				in_skills = True
				continue
			if in_skills:
				if any(h in lower.rstrip(":") for h in self.SECTION_HEADERS):
					in_skills = False
				else:
					skill_section += line + " "

		if skill_section:
			skills = [s.strip() for s in re.split(r"[,;|\n•*]|\s+-\s+", skill_section) if s.strip() and len(s.strip()) > 1]
		return skills

	def _extract_project_skills(self, text):
		skills = []
		project_section = ""
		in_projects = False
		lines = text.split("\n")
		for line in lines:
			lower = line.lower().strip()
			if lower in ["projects", "personal projects", "side projects"]:
				in_projects = True
				continue
			if in_projects:
				if any(h in lower for h in self.SECTION_HEADERS):
					in_projects = False
				else:
					project_section += line + " "

		if project_section:
			skills = [s.strip() for s in re.split(r"[,;|\n•*]|\s+-\s+", project_section) if s.strip() and len(s.strip()) > 1]
		return skills

	def _extract_experience_skills(self, text):
		skills = []
		exp_section = ""
		in_exp = False
		lines = text.split("\n")
		for line in lines:
			lower = line.lower().strip()
			if lower in ["experience", "work experience", "professional experience"]:
				in_exp = True
				continue
			if in_exp:
				if any(h in lower for h in self.SECTION_HEADERS):
					in_exp = False
				else:
					exp_section += line + " "

		if exp_section:
			skills = [s.strip() for s in re.split(r"[,;|\n•*]|\s+-\s+", exp_section) if s.strip() and len(s.strip()) > 1]
		return skills

	def _extract_technologies(self, text):
		tech_keywords = [
			"python", "java", "javascript", "typescript", "react", "angular", "vue",
			"node", "django", "flask", "spring", "sql", "nosql", "mongodb", "postgresql",
			"aws", "azure", "gcp", "docker", "kubernetes", "terraform", "git",
			"machine learning", "deep learning", "tensorflow", "pytorch", "nlp",
			"data science", "analytics", "tableau", "power bi", "excel",
			"agile", "scrum", "ci/cd", "rest", "graphql", "microservices",
		]
		found = []
		text_lower = text.lower()
		for tech in tech_keywords:
			if tech in text_lower:
				found.append(tech)
		return found

	def _extract_tools(self, text):
		tool_keywords = [
			"jira", "confluence", "figma", "photoshop", "illustrator",
			"salesforce", "hubspot", "slack", "notion", "asana",
			"postman", "swagger", "jenkins", "github", "gitlab",
		]
		found = []
		text_lower = text.lower()
		for tool in tool_keywords:
			if tool in text_lower:
				found.append(tool)
		return found

	def _extract_employers(self, text):
		employers = []
		lines = text.split("\n")
		for line in lines:
			if " at " in line or " @ " in line:
				parts = re.split(r"\s+at\s+|\s+@\s+", line)
				if len(parts) > 1:
					employers.append(parts[-1].strip())
		return list(set(employers))

	def _extract_titles(self, text):
		titles = []
		lines = text.split("\n")
		for line in lines:
			if any(marker in line for marker in [" at ", " @ ", " | "]):
				title_part = re.split(r"\s+at\s+|\s+@\s+|\s+\|\s+", line)[0].strip()
				if title_part and len(title_part) < 60:
					titles.append(title_part)
		return list(set(titles))

	def _extract_education_entries(self, text):
		entries = []
		lines = text.split("\n")
		in_edu = False
		for line in lines:
			lower = line.lower().strip()
			if lower in ["education", "academic background"]:
				in_edu = True
				continue
			if in_edu:
				if any(h in lower for h in self.SECTION_HEADERS):
					in_edu = False
				else:
					entries.append(line.strip())
		return [e for e in entries if e]

	def _extract_certifications(self, text):
		certs = []
		lines = text.split("\n")
		in_cert = False
		for line in lines:
			lower = line.lower().strip()
			if lower in ["certifications", "certificates", "credentials"]:
				in_cert = True
				continue
			if in_cert:
				if any(h in lower for h in self.SECTION_HEADERS):
					in_cert = False
				else:
					certs.append(line.strip())
		return [c for c in certs if c]

	def _extract_achievements(self, text):
		achievements = []
		lines = text.split("\n")
		for line in lines:
			bullet = re.sub(r"^[-•*]\s*", "", line).strip()
			if any(kw in bullet.lower() for kw in ["increased", "decreased", "improved", "saved", "generated", "reduced", "grew", "managed", "led", "delivered", "achieved"]):
				achievements.append(bullet)
		return achievements[:10]

	def _extract_metrics(self, text):
		patterns = [
			r"\$[\d,]+(?:\.\d+)?[kmbKMB]?",
			r"\d+(?:\.\d+)?%",
			r"\d+(?:\.\d+)?[kmbKMB]?\+?\s+(?:users|customers|clients|projects|team members|employees)",
			r"(?:increased|decreased|improved|saved|reduced|grew)\s+.*?\d+",
			r"\d+(?:\.\d+)?x\s+(?:growth|increase|improvement)",
		]
		metrics = []
		for pattern in patterns:
			matches = re.findall(pattern, text, re.IGNORECASE)
			metrics.extend(matches)
		return list(set(metrics))[:20]

	def _extract_project_names(self, text):
		names = []
		lines = text.split("\n")
		in_proj = False
		for line in lines:
			lower = line.lower().strip()
			if lower in ["projects", "personal projects", "side projects"]:
				in_proj = True
				continue
			if in_proj:
				if any(h in lower for h in self.SECTION_HEADERS):
					in_proj = False
				else:
					cleaned = re.sub(r"^[-•*]\s*", "", line).strip()
					if cleaned and len(cleaned) < 80:
						names.append(cleaned)
		return names[:10]

	def resume_to_text(self, resume):
		"""Convert ParsedResume to plain text with standard section headers."""
		parts = []
		contact = getattr(resume, "contact", None)
		if contact:
			header = " | ".join(
				filter(
					None,
					[
						getattr(contact, "name", None),
						getattr(contact, "email", None),
						getattr(contact, "phone", None),
						getattr(contact, "linkedin", None),
						getattr(contact, "github", None),
						getattr(contact, "location", None),
					],
				)
			)
			if header:
				parts.append(header)

		if resume.summary:
			parts.append("SUMMARY")
			parts.append(resume.summary)

		if resume.experience:
			parts.append("EXPERIENCE")
			for exp in resume.experience:
				line = " ".join(filter(None, [exp.title, f"at {exp.company}" if exp.company else ""]))
				parts.append(line.strip())
				for b in exp.description:
					parts.append(f"- {b}")
				for a in exp.achievements:
					parts.append(f"- {a}")

		if resume.projects:
			parts.append("PROJECTS")
			for proj in resume.projects:
				parts.append(proj.name)
				if proj.description:
					parts.append(f"- {proj.description}")
				for h in proj.highlights or []:
					parts.append(f"- {h}")
				if proj.technologies:
					parts.append("- Technologies: " + ", ".join(proj.technologies))

		if resume.skills:
			parts.append("SKILLS")
			parts.append(", ".join(s.name for s in resume.skills if s.name))

		if resume.education:
			parts.append("EDUCATION")
			for edu in resume.education:
				parts.append(" ".join(filter(None, [edu.degree, edu.field_of_study, edu.institution])))

		if resume.certifications:
			parts.append("CERTIFICATIONS")
			parts.append(", ".join(c.name for c in resume.certifications if c.name))

		return "\n".join(parts)


# Words and product names used to put spaces back into text that a PDF
# extractor or a small model glued together.
_KEEP_TERMS = {
	"react.js": "React.js",
	"reactjs": "React.js",
	"node.js": "Node.js",
	"nodejs": "Node.js",
	"express.js": "Express.js",
	"next.js": "Next.js",
	"vue.js": "Vue.js",
	"javascript": "JavaScript",
	"typescript": "TypeScript",
	"fastapi": "FastAPI",
	"postgresql": "PostgreSQL",
	"postgres": "PostgreSQL",
	"sqlalchemy": "SQLAlchemy",
	"mongodb": "MongoDB",
	"mysql": "MySQL",
	"graphql": "GraphQL",
	"langchain": "LangChain",
	"maplibre": "MapLibre",
	"maplibregl": "MapLibre GL",
	"github": "GitHub",
	"gitlab": "GitLab",
	"linkedin": "LinkedIn",
	"leetcode": "LeetCode",
	"tensorflow": "TensorFlow",
	"pytorch": "PyTorch",
	"scikit-learn": "Scikit-learn",
	"sklearn": "Scikit-learn",
	"springboot": "Spring Boot",
	"spring": "Spring",
	"html5": "HTML5",
	"css3": "CSS3",
	"tailwind": "Tailwind",
	"tailwindcss": "Tailwind CSS",
	"docker": "Docker",
	"kubernetes": "Kubernetes",
	"jenkins": "Jenkins",
	"pytest": "Pytest",
	"junit": "JUnit",
	"qdrant": "Qdrant",
	"redis": "Redis",
	"numpy": "NumPy",
	"pandas": "Pandas",
	"aws": "AWS",
	"awsec2": "AWS EC2",
	"azure": "Azure",
	"gcp": "GCP",
	"jwt": "JWT",
	"rag": "RAG",
	"llm": "LLM",
	"llms": "LLMs",
	"api": "API",
	"apis": "APIs",
	"rest": "REST",
	"sql": "SQL",
	"css": "CSS",
	"html": "HTML",
	"json": "JSON",
	"http": "HTTP",
	"https": "HTTPS",
	"tcp": "TCP",
	"ip": "IP",
	"vlan": "VLAN",
	"vlans": "VLANs",
	"itsm": "ITSM",
	"csa": "CSA",
	"nptel": "NPTEL",
	"nasscom": "NASSCOM",
	"aicte": "AICTE",
	"cgpa": "CGPA",
	"ci/cd": "CI/CD",
	"tcp/ip": "TCP/IP",
	"genai": "GenAI",
	"devops": "DevOps",
	"githubactions": "GitHub Actions",
	"servicenow": "ServiceNow",
	"smartbridge": "SmartBridge",
	"futureskills": "FutureSkills",
	"geeksforgeeks": "GeeksforGeeks",
	"eduskills": "EduSkills",
	"qlik": "Qlik",
	"packettracer": "Packet Tracer",
}

_WORDS = set(
	"""
	a an the and or of to for in on at by with from into over under about as is are was were be been being
	this that these those it its their his her our your my we you they i
	full stack real time flight tracking platform using featuring interactive map integrated aviation data
	display live aircraft positions airport information developed powered assistant tool calling structured
	outputs leveraging embeddings vector store context grounded semantic question answering architected
	backend exposing secured authentication containerized deployed engineered including recommendation plant
	disease detection chatbot weather forecasting deliver driven farming insights built end persistent storage
	incorporated market price analysis functionality implemented multilingual voice assistance task management
	farmer community forum within modular extensible architecture designed enterprise network configuring
	routing switching addressing multilayer logical segmentation configured inter routing subnetting validating
	connectivity across network segments completed credentials automated workflows components business rules
	client scripts catalog earned certified system administrator certification badges covering application
	development scripting generative achieved industry recognized solved problems final year computer science
	undergraduate expertise hands experience building applications strong foundation structures algorithms
	databases cloud technologies scalable based intelligent smart agriculture platform source code demo
	virtual internship academy university certificate project credentials introduction operating systems elite
	machine learning gold computing future skills prime google developers education hyderabad b tech engineering
	languages frontend backend tools other soft communication collaboration problem solving critical thinking
	adaptability attention detail leadership initiative ownership professional summary technical skills projects
	achievements certifications contact portfolio present current remote india
	using via per each such than then also only both most more some any all not but if so
	while where when what which who how can will may has have had do does did done
	new one two three four five six seven eight nine ten
	real-time end-to-end full-stack
	information positions question answering exposing modules crop insights packet tracer
	implementing dashboard climate impact hackathon recognized components business rules
	scripts catalog administrator badges generative workflows configuring subnetting segments
	enterprise addressing switching segmentation connectivity validating multilayer logical
	voice forum extensible functionality storage persistent recommendation powered tool
	calling outputs aircraft airport gemini vector semantic grounded context
	jwt rest api apis sql aws rag llm tech science engineering computer in developed secured
	display live to and with over for the an a of on indexing sharding balancing queues
	message load caching networks operating systems design virtual academy networking
	""".split()
)

_TERM_KEYS = sorted(_KEEP_TERMS, key=len, reverse=True)


def restore_resume_spacing(text: str) -> str:
	"""Rejoin line-break hyphens and split words that were glued together."""
	if not text:
		return text
	text = text.replace("\u00ad", "")
	text = text.replace("\ufffd", " ")
	text = re.sub(r"-\s*\n\s*(?=[a-z])", "", text)
	lines = [_restore_line(line) for line in text.split("\n")]
	return "\n".join(lines)


def _restore_line(line: str) -> str:
	if not line.strip():
		return line
	protected: list[str] = []

	def _hold(match: re.Match) -> str:
		protected.append(match.group(0))
		return f"\x00{len(protected) - 1}\x00"

	line = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", _hold, line)
	line = re.sub(r"https?://\S+", _hold, line)
	line = re.sub(r",(?=\S)", ", ", line)
	line = re.sub(r";(?=\S)", "; ", line)
	line = re.sub(r":(?!//)(?=\S)", ": ", line)
	line = re.sub(
		r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)(\d{4})\b",
		r"\1 \2",
		line,
		flags=re.IGNORECASE,
	)
	parts = [_restore_token(token) for token in line.split()]
	restored = " ".join(parts)
	for index, value in enumerate(protected):
		restored = restored.replace(f"\x00{index}\x00", value)
	return restored


def _restore_token(token: str) -> str:
	if not token or "@" in token or "://" in token:
		return token
	match = re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", token)
	if not match:
		return token
	lead, core, tail = match.groups()
	if not core:
		return token
	return f"{lead}{_restore_core(core)}{tail}"


def _term_at(lower: str, index: int) -> str:
	for term in _TERM_KEYS:
		if len(term) >= 4 and lower.startswith(term, index):
			return term
	return ""


def _looks_like_link(core: str) -> bool:
	lower = core.lower()
	if "://" in lower or "@" in lower:
		return True
	return bool(re.search(r"\.(?:com|org|io|dev|net|in|edu|ai)(?:/|$)", lower))


def _restore_core(core: str) -> str:
	if core.lower() in _KEEP_TERMS:
		return _KEEP_TERMS[core.lower()]
	if _looks_like_link(core):
		return core
	lower = core.lower()
	chunks: list[str] = []
	index = 0
	while index < len(core):
		term = _term_at(lower, index)
		if term:
			chunks.append(_KEEP_TERMS[term])
			index += len(term)
			continue
		end = index + 1
		while end < len(core) and not _term_at(lower, end):
			end += 1
		chunks.append(_restore_gap(core[index:end]))
		index = end
	return " ".join(chunk for chunk in chunks if chunk)


def _restore_gap(gap: str) -> str:
	if not gap:
		return gap
	if gap.lower() in _KEEP_TERMS:
		return _KEEP_TERMS[gap.lower()]
	if "-" in gap and not re.search(r"[/&.]", gap):
		bits = [_restore_gap(bit) for bit in gap.split("-") if bit]
		if not bits:
			return gap
		joined = bits[0]
		for nxt in bits[1:]:
			if " " not in joined and " " not in nxt:
				joined = f"{joined}-{nxt}"
			elif " " not in nxt:
				head, _, tail = joined.rpartition(" ")
				joined = f"{head} {tail}-{nxt}" if head else f"{tail}-{nxt}"
			else:
				head, _, tail = joined.rpartition(" ")
				first, _, rest = nxt.partition(" ")
				middle = f"{tail}-{first}" if tail else first
				joined = " ".join(part for part in (head, middle, rest) if part)
		return joined
	if re.search(r"[/&.]", gap):
		parts = re.split(r"([/&.])", gap)
		rebuilt = []
		for part in parts:
			if part in "/&.":
				rebuilt.append(part)
			else:
				rebuilt.append(_restore_gap(part))
		text = "".join(rebuilt)
		text = re.sub(r"\s*&\s*", " & ", text)
		text = re.sub(r"(?<=[A-Za-z])\s*/\s*(?=[A-Za-z])", " / ", text)
		text = re.sub(r"(?<=[A-Za-z])/(?=[A-Za-z])", " / ", text)
		return re.sub(r"\s+", " ", text).strip()
	camel = _split_camel(gap)
	if camel != gap:
		return " ".join(_restore_gap(part) for part in camel.split())
	return _segment_letters(gap)


def _known_piece(text: str) -> bool:
	key = (text or "").lower()
	return bool(key) and (key in _WORDS or key in _KEEP_TERMS)


def _split_camel(gap: str) -> str:
	"""Break CamelCase and acronyms without splitting TypeScript or API."""
	if gap.lower() in _KEEP_TERMS or _known_piece(gap):
		return gap
	# DBIndexing -> DB + Indexing, when the word is known
	for index in range(2, len(gap) - 2):
		left, right = gap[:index], gap[index:]
		if not left.isupper() or not right[:1].isupper():
			continue
		word = re.match(r"[A-Z][a-z]+", right)
		if word and _known_piece(word.group(0)):
			return f"{left} {right}"
	# APIand / RAGandembeddings -> API + and...
	match = re.match(r"^([A-Z]{2,})([a-z].+)$", gap)
	if match and (_known_piece(match.group(2)) or " " in _segment_letters(match.group(2))):
		return f"{match.group(1)} {match.group(2)}"
	if re.search(r"[a-z][A-Z]", gap):
		parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", gap).split()
		if parts and all(_known_piece(part) or part.isupper() for part in parts):
			return " ".join(parts)
	return gap


def _segment_letters(chunk: str) -> str:
	"""Split a glued letter run only when every piece is a known word."""
	if len(chunk) < 6 or not chunk.isalpha():
		return chunk
	if chunk.lower() in _WORDS or chunk.lower() in _KEEP_TERMS:
		return _KEEP_TERMS.get(chunk.lower(), chunk)
	lower = chunk.lower()
	size = len(lower)
	best = [10 ** 9] * (size + 1)
	prev = [-1] * (size + 1)
	best[0] = 0
	for start in range(size):
		if best[start] >= 10 ** 9:
			continue
		for end in range(start + 1, min(size, start + 24) + 1):
			word = lower[start:end]
			if end - start == 1 and word not in {"a", "i"}:
				continue
			if word not in _WORDS and word not in _KEEP_TERMS:
				continue
			cost = best[start] + max(1, 16 - (end - start))
			if cost < best[end]:
				best[end] = cost
				prev[end] = start
	if best[size] >= 10 ** 9:
		return chunk
	spans: list[tuple[int, int]] = []
	cursor = size
	while cursor > 0:
		start = prev[cursor]
		if start < 0 or cursor - start < 1:
			return chunk
		if cursor - start == 1 and lower[start:cursor] not in {"a", "i"}:
			return chunk
		spans.append((start, cursor))
		cursor = start
	if len(spans) < 2:
		return chunk
	spans.reverse()
	return " ".join(chunk[start:end] for start, end in spans)
