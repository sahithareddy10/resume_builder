"""
PDF Generation Service: one-page, single-column resumes in the compact template.

Layout:
- Centered uppercase name and a pipe-separated contact line
- Sections in order: Summary, Skills, Experience, Projects, Education,
  Certifications, Achievements
- Bold section titles with a full-width rule
- Dates, CGPA, and links sit on the right of their row
"""

from io import BytesIO
import html
import re
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
	BaseDocTemplate,
	Frame,
	HRFlowable,
	PageTemplate,
	Paragraph,
	Spacer,
	Table,
	TableStyle,
)

from app.services.resume_parser import restore_resume_spacing


def separate_resume_sections(text: str) -> str:
	"""Turn a one-paragraph resume into real section lines before layout."""
	text = text or ""
	text = re.sub(r"(?i)\bpage\s+\d+\s*(?:\|\s*\d+)?", " ", text)
	text = re.sub(r"\s*[•●]\s*", "\n• ", text)
	headings = (
		"technical proficiencies",
		"core competencies",
		"technical skills",
		"professional summary",
		"career experience",
		"professional experience",
		"work experience",
		"career experience",
		"internship experience",
		"soft skills",
		"awards and recognition",
		"awards & recognition",
		"projects",
		"education",
		"certifications",
		"achievements",
		"summary",
	)
	pattern = r"(?i)(?<![A-Za-z])(" + "|".join(headings) + r")(?![A-Za-z])\s*:?"
	aliases = {
		"TECHNICAL PROFICIENCIES": "TECHNICAL SKILLS",
		"CORE COMPETENCIES": "TECHNICAL SKILLS",
		"CAREER EXPERIENCE": "PROFESSIONAL EXPERIENCE",
		"SUMMARY": "PROFESSIONAL SUMMARY",
		"AWARDS AND RECOGNITION": "ACHIEVEMENTS",
		"AWARDS & RECOGNITION": "ACHIEVEMENTS",
	}

	def repl(match: re.Match) -> str:
		title = aliases.get(match.group(1).upper(), match.group(1).upper())
		return f"\n{title}\n"

	text = re.sub(pattern, repl, text)
	text = re.sub(r"[ \t]+\n", "\n", text)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


class PDFGenerator:
	"""Generates clean, professional resume PDFs."""

	TEXT_COLOR = colors.HexColor("#111111")
	HEADING_COLOR = colors.HexColor("#111111")
	MUTED = colors.HexColor("#333333")
	LINK_COLOR = colors.HexColor("#1d4ed8")
	DIVIDER_COLOR = colors.HexColor("#111111")
	_DISPLAY = {
		"PROFESSIONAL SUMMARY": "Summary",
		"TECHNICAL SKILLS": "Technical Skills",
		"SOFT SKILLS": "Soft Skills",
		"PROJECTS": "Projects",
		"PROFESSIONAL EXPERIENCE": "Professional Experience",
		"INTERNSHIP EXPERIENCE": "Internship Experience",
		"EDUCATION": "Education",
		"CERTIFICATIONS": "Certifications & Credentials",
		"ACHIEVEMENTS": "Achievements",
	}

	_HEADINGS = {
		"contact": "CONTACT",
		"contact information": "CONTACT",
		"professional summary": "PROFESSIONAL SUMMARY",
		"summary": "PROFESSIONAL SUMMARY",
		"profile": "PROFESSIONAL SUMMARY",
		"objective": "PROFESSIONAL SUMMARY",
		"technical skills": "TECHNICAL SKILLS",
		"technical proficiencies": "TECHNICAL SKILLS",
		"core competencies": "TECHNICAL SKILLS",
		"skills": "TECHNICAL SKILLS",
		"soft skills": "SOFT SKILLS",
		"projects": "PROJECTS",
		"personal projects": "PROJECTS",
		"professional experience": "PROFESSIONAL EXPERIENCE",
		"work experience": "PROFESSIONAL EXPERIENCE",
		"experience": "PROFESSIONAL EXPERIENCE",
		"career experience": "PROFESSIONAL EXPERIENCE",
		"internship experience": "INTERNSHIP EXPERIENCE",
		"internships": "INTERNSHIP EXPERIENCE",
		"education": "EDUCATION",
		"certifications": "CERTIFICATIONS",
		"certifications credentials": "CERTIFICATIONS",
		"certifications and credentials": "CERTIFICATIONS",
		"certificates": "CERTIFICATIONS",
		"achievements": "ACHIEVEMENTS",
		"awards": "ACHIEVEMENTS",
		"awards and recognition": "ACHIEVEMENTS",
		"awards recognition": "ACHIEVEMENTS",
	}
	_ORDER = [
		"PROFESSIONAL SUMMARY",
		"TECHNICAL SKILLS",
		"SOFT SKILLS",
		"PROFESSIONAL EXPERIENCE",
		"INTERNSHIP EXPERIENCE",
		"PROJECTS",
		"EDUCATION",
		"CERTIFICATIONS",
		"ACHIEVEMENTS",
	]
	_JUNK = {
		"plaintext",
		"plain text",
		"text",
		"markdown",
		"resume",
		"optimized resume",
		"enhanced resume",
		"contact",
		"contact information",
	}
	_BULLET = re.compile(r"^[\-\*\u2022\u2023\u25cf\u25aa\u25e6\uf0b7\u00b7]+\s*")
	_DATE = re.compile(
		r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\s*[\u2013\u2014\-]\s*"
		r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|\d{4})"
		r"|\b20\d{2}\s*[\u2013\u2014\-]\s*(?:20\d{2}|Present))",
		re.IGNORECASE,
	)
	_NOT_A_NAME = {
		"technical", "proficiencies", "proficiency", "summary", "skills", "skill",
		"experience", "education", "projects", "project", "certifications",
		"achievements", "page", "resume", "profile", "objective", "competencies",
	}
	_ENTRY_SECTIONS = {
		"PROJECTS",
		"INTERNSHIP EXPERIENCE",
		"PROFESSIONAL EXPERIENCE",
		"EDUCATION",
		"CERTIFICATIONS",
		"ACHIEVEMENTS",
	}
	_GPA = re.compile(
		r"((?:CGPA|GPA|Grade)\s*[:.]?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)",
		re.IGNORECASE,
	)
	_LINK_TOKEN = re.compile(
		r"^(source code|live demo|certificate|view|project\s*(?:&|and)\s*credentials|github|portfolio)$",
		re.IGNORECASE,
	)
	_SCHOOL = re.compile(r"\b(university|college|institute|school|academy)\b", re.IGNORECASE)

	def __init__(self, template: str = "professional"):
		self.template = template

	def generate(self, resume_text: str, sections: Optional[dict] = None) -> bytes:
		"""Generate a resume PDF from optimized text. Returns bytes."""
		buffer = BytesIO()
		self._build_single_column(separate_resume_sections(restore_resume_spacing(resume_text or "")), buffer)
		return buffer.getvalue()

	def _setup_styles(self):
		base = getSampleStyleSheet()
		name = ParagraphStyle(
			"Name",
			parent=base["Normal"],
			fontName="Helvetica-Bold",
			fontSize=15,
			leading=18,
			alignment=TA_CENTER,
			textColor=self.HEADING_COLOR,
			spaceAfter=1,
		)
		contact = ParagraphStyle(
			"Contact",
			parent=base["Normal"],
			fontName="Helvetica",
			fontSize=8,
			leading=10,
			alignment=TA_CENTER,
			textColor=self.TEXT_COLOR,
			spaceAfter=6,
		)
		section = ParagraphStyle(
			"SectionHeading",
			parent=base["Normal"],
			fontName="Helvetica-Bold",
			fontSize=11,
			leading=13,
			alignment=TA_LEFT,
			textColor=self.HEADING_COLOR,
			spaceBefore=7,
			spaceAfter=0,
		)
		body = ParagraphStyle(
			"Body",
			parent=base["Normal"],
			fontName="Helvetica",
			fontSize=9,
			leading=11.5,
			textColor=self.TEXT_COLOR,
			spaceAfter=1,
		)
		bullet = ParagraphStyle(
			"Bullet",
			parent=base["Normal"],
			fontName="Helvetica",
			fontSize=9,
			leading=11.5,
			textColor=self.TEXT_COLOR,
			leftIndent=12,
			bulletIndent=0,
			spaceAfter=1,
		)
		title = ParagraphStyle(
			"EntryTitle",
			parent=base["Normal"],
			fontName="Helvetica-Bold",
			fontSize=10,
			leading=12,
			textColor=self.TEXT_COLOR,
			spaceBefore=4,
			spaceAfter=0,
		)
		meta = ParagraphStyle(
			"EntryMeta",
			parent=base["Normal"],
			fontName="Helvetica-Oblique",
			fontSize=9,
			leading=11,
			textColor=self.TEXT_COLOR,
			spaceAfter=1,
		)
		right = ParagraphStyle(
			"RightMeta",
			parent=base["Normal"],
			fontName="Helvetica",
			fontSize=9,
			leading=11,
			alignment=TA_RIGHT,
			textColor=self.TEXT_COLOR,
			spaceAfter=0,
		)
		link = ParagraphStyle(
			"Link",
			parent=base["Normal"],
			fontName="Helvetica",
			fontSize=8.5,
			leading=11,
			alignment=TA_RIGHT,
			textColor=self.LINK_COLOR,
			spaceBefore=1,
			spaceAfter=1,
		)
		return {
			"name": name,
			"contact": contact,
			"section": section,
			"body": body,
			"bullet": bullet,
			"title": title,
			"meta": meta,
			"right": right,
			"link": link,
		}

	def _build_single_column(self, resume_text: str, buffer: BytesIO) -> None:
		styles = self._setup_styles()
		doc = BaseDocTemplate(
			buffer,
			pagesize=letter,
			leftMargin=0.5 * inch,
			rightMargin=0.5 * inch,
			topMargin=0.42 * inch,
			bottomMargin=0.42 * inch,
		)
		frame = Frame(
			doc.leftMargin,
			doc.bottomMargin,
			doc.width,
			doc.height,
			leftPadding=0,
			rightPadding=0,
			topPadding=0,
			bottomPadding=0,
		)
		doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

		sections = self._parse_sections(resume_text)
		name, contact_lines, summary_extra = self._peel_header(sections)
		if summary_extra and not sections.get("PROFESSIONAL SUMMARY"):
			sections["PROFESSIONAL SUMMARY"] = summary_extra
		elif sections.get("PROFESSIONAL SUMMARY"):
			sections["PROFESSIONAL SUMMARY"] = [
				cleaned for line in sections["PROFESSIONAL SUMMARY"]
				if (cleaned := self._strip_identity_prefix(line, name))
			]

		story = []
		if name:
			story.append(Paragraph(self._esc(name.upper()), styles["name"]))
		if contact_lines:
			story.append(Paragraph(self._esc("  |  ".join(contact_lines)), styles["contact"]))
		elif name:
			story.append(Spacer(1, 4))

		width = doc.width
		for key in self._ORDER:
			lines = self._clean_lines(sections.get(key, []))
			if not lines:
				continue
			story.append(Paragraph(self._esc(self._DISPLAY.get(key, key)), styles["section"]))
			story.append(HRFlowable(
				width="100%",
				thickness=0.8,
				color=self.DIVIDER_COLOR,
				spaceBefore=1,
				spaceAfter=3,
			))
			if key in {"PROFESSIONAL SUMMARY", "SOFT SKILLS"}:
				story.append(Paragraph(self._esc(" ".join(lines)), styles["body"]))
			elif key == "TECHNICAL SKILLS":
				for line in lines:
					story.append(Paragraph(self._skill_markup(line), styles["body"]))
			elif key == "EDUCATION":
				story.extend(self._education_flowables(lines, styles, width))
			elif key == "CERTIFICATIONS":
				story.extend(self._credential_flowables(lines, styles, width))
			elif key in self._ENTRY_SECTIONS:
				story.extend(self._entry_flowables(lines, styles, width, projects=(key == "PROJECTS")))
			else:
				for line in lines:
					story.append(Paragraph(self._esc(line), styles["body"]))

		if not story:
			story.append(Paragraph(self._esc(resume_text.strip() or "Resume"), styles["body"]))
		doc.build(story)

	def _parse_sections(self, text: str) -> dict:
		sections: dict[str, list[str]] = {"HEADER": []}
		current = "HEADER"
		for raw in (text or "").splitlines():
			line = raw.strip()
			if not line or line.lower() in self._JUNK:
				continue
			heading = self._heading_name(line)
			if heading:
				current = heading
				sections.setdefault(current, [])
				continue
			sections.setdefault(current, []).append(line)
		return sections

	def _heading_name(self, line: str) -> Optional[str]:
		if len(line) > 48 or self._BULLET.match(line):
			return None
		norm = re.sub(r"[&/]", " ", line.lower())
		norm = re.sub(r"[^a-z ]+", " ", norm)
		norm = re.sub(r"\s+", " ", norm).strip()
		return self._HEADINGS.get(norm)

	def _peel_header(self, sections: dict) -> tuple[str, list[str], list[str]]:
		name = ""
		contact: list[str] = []
		prose: list[str] = []
		seen = set()
		for key in ("HEADER", "CONTACT", "PROFESSIONAL SUMMARY"):
			kept = []
			for line in sections.get(key, []):
				if line.lower() in self._JUNK:
					continue
				marker = line.lower()
				if marker in seen:
					continue
				if not name and self._is_name(line):
					name = line
					seen.add(marker)
					continue
				found_name = self._name_before_contact(line)
				contact_bits = self._contact_bits(line)
				if found_name and not name:
					name = found_name
				if self._is_identity_line(line, name or found_name):
					if contact_bits:
						contact.extend(contact_bits)
					seen.add(marker)
					continue
				if contact_bits:
					contact.extend(contact_bits)
					seen.add(marker)
					continue
				if self._is_contact(line):
					contact.append(self._trim_contact(line))
					seen.add(marker)
					continue
				if key == "PROFESSIONAL SUMMARY":
					kept.append(line)
				else:
					prose.append(line)
				seen.add(marker)
			if key == "PROFESSIONAL SUMMARY":
				sections[key] = kept
		for key, lines in list(sections.items()):
			if key in {"HEADER", "CONTACT"}:
				continue
			kept = []
			for line in lines:
				found_name = self._name_before_contact(line)
				contact_bits = self._contact_bits(line)
				is_identity = bool(contact_bits) or (
					bool(found_name) and bool(re.search(r"\b[A-Z]{2}\b|\d{5}|@", line)) and len(line.split()) <= 12
				)
				if not is_identity:
					kept.append(self._strip_identity_prefix(line, name or found_name) or line)
					continue
				if found_name and not name:
					name = found_name
				contact.extend(contact_bits)
			sections[key] = kept
		deduped = []
		seen_bits = set()
		for bit in contact:
			marker = bit.lower()
			if marker in seen_bits:
				continue
			seen_bits.add(marker)
			deduped.append(bit)
		return name, deduped, prose

	def _is_name(self, line: str) -> bool:
		if self._is_contact(line) or ":" in line or len(line) > 40:
			return False
		words = line.split()
		if not 2 <= len(words) <= 4:
			return False
		if any(ch.isdigit() for ch in line):
			return False
		if any(word.lower().strip(".:") in self._NOT_A_NAME for word in words):
			return False
		return all(word[:1].isupper() for word in words)

	def _is_identity_line(self, line: str, name: str) -> bool:
		"""A short name, city, or zip line does not belong in the summary."""
		text = " ".join((line or "").split())
		if not text or len(text.split()) > 14:
			return False
		if name and text.lower().startswith(name.lower()) and len(text.split()) <= len(name.split()) + 6:
			return True
		if re.search(r"\b[A-Z]{2}\s+\d{5}\b", text) and len(text.split()) <= 12:
			return True
		if re.search(r",\s*[A-Z]{2}\b", text) and len(text.split()) <= 10 and "@" not in text:
			if self._name_before_contact(text):
				return True
		return False

	def _strip_identity_prefix(self, line: str, name: str) -> str:
		text = " ".join((line or "").split())
		if name:
			text = re.sub(rf"^{re.escape(name)}\b[\s,|-]*", "", text, flags=re.I)
		text = re.sub(r"^[A-Z][a-zA-Z.]*,\s*[A-Z]{2}(?:\s+\d{5})?\b[\s,|-]*", "", text)
		text = re.sub(r"^[A-Z]{2}\s+\d{5}\b[\s,|-]*", "", text)
		return text.strip(" ,|-")

	def _name_before_contact(self, line: str) -> str:
		head = re.split(r"\s+[•|]\s+|\s+\(?\d{3}\)?|\s+\S+@\S+", line, maxsplit=1)[0]
		head = re.sub(r",?\s+[A-Z][a-zA-Z.]*,?\s+[A-Z]{2}\b.*", "", head)
		head = re.sub(r"\s+\d{5}.*", "", head).strip(" ,|")
		words = [word for word in re.split(r"\s+", head) if word]
		if not 2 <= len(words) <= 4:
			return ""
		if any(any(ch.isdigit() for ch in word) for word in words):
			return ""
		if any(word.lower().strip(".:") in self._NOT_A_NAME for word in words):
			return ""
		if not all(word[:1].isupper() for word in words):
			return ""
		return " ".join(words)

	def _contact_bits(self, line: str) -> list[str]:
		bits = []
		phone = re.search(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}", line)
		email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", line)
		links = re.findall(r"(?:https?://)?(?:www\.)?(?:linkedin|github|leetcode)\S*", line, flags=re.IGNORECASE)
		if phone:
			bits.append(phone.group(0))
		if email:
			bits.append(email.group(0))
		for link in links:
			cleaned = link.strip(" |,;")
			if cleaned not in bits:
				bits.append(cleaned)
		return bits

	def _trim_contact(self, line: str) -> str:
		line = re.sub(r"(?i)\bpage\s*\d+\b", "", line)
		return re.sub(r"\s+\|\s*$", "", re.sub(r"\s{2,}", " ", line)).strip(" |")

	def _is_contact(self, line: str) -> bool:
		"""True for a short contact line, never for a summary sentence."""
		words = line.split()
		if len(words) > 16 or len(line) > 180:
			return False
		lower = line.lower()
		if re.search(r"\b(targeting|demonstrated|undergraduate|hands-on|expertise|foundation)\b", lower):
			return False
		if line.rstrip().endswith(".") and len(words) > 8:
			return False
		has_email = "@" in line
		has_phone = bool(re.search(r"\+?\d[\d\-\s()]{8,}\d", line))
		link_labels = sum(label in lower for label in ("linkedin", "github", "leetcode", "portfolio"))
		if has_email or has_phone:
			return True
		if link_labels and len(words) <= 12:
			return True
		return "|" in line and len(words) <= 10

	def _clean_lines(self, lines: list[str]) -> list[str]:
		merged: list[str] = []
		for line in lines:
			line = line.strip()
			if not line or line.lower() in self._JUNK:
				continue
			if (
				merged
				and not self._BULLET.match(line)
				and not self._BULLET.match(merged[-1])
				and merged[-1][-1] not in ".!?:;"
				and line[0].islower()
			):
				merged[-1] = f"{merged[-1]} {line}"
				continue
			if merged and self._BULLET.match(merged[-1]) and not self._BULLET.match(line) and merged[-1][-1] not in ".!?":
				merged[-1] = f"{merged[-1]} {line}"
				continue
			merged.append(line)
		return merged

	def _entry_flowables(self, lines: list[str], styles: dict, width: float, projects: bool = False) -> list:
		flowables = []
		for entry in self._group_entries(lines):
			title, date = self._split_date(entry["title"])
			meta = list(entry["meta"])
			links = list(entry.get("links") or [])
			tech = ""
			if projects and meta and self._is_tech_line(meta[0]):
				tech = meta.pop(0)
			if title:
				flowables.append(self._lr(
					f"<b>{self._esc(title)}</b>",
					self._esc(date),
					styles["title"],
					styles["right"],
					width,
				))
			org = meta.pop(0) if meta else ""
			if projects and tech:
				flowables.append(Paragraph(self._esc(tech), styles["meta"]))
			elif org:
				right_html = self._link_markup(" | ".join(links)) if (links and not projects) else ""
				if not projects and links:
					links = []
				flowables.append(self._lr(
					f"<i>{self._esc(org)}</i>",
					right_html,
					styles["meta"],
					styles["link"],
					width,
				))
			for extra in meta:
				if self._is_tech_line(extra):
					flowables.append(Paragraph(self._esc(extra), styles["meta"]))
				else:
					flowables.append(Paragraph(self._esc(extra), styles["body"]))
			bullets = list(entry["bullets"])
			if projects and bullets and (
				bullets[0].lower().startswith("technologies:") or self._is_tech_line(bullets[0])
			):
				tech_bullet = re.sub(r"(?i)^technologies:\s*", "", bullets.pop(0))
				flowables.append(Paragraph(self._esc(tech_bullet), styles["meta"]))
			for bullet in bullets:
				flowables.append(Paragraph(f"•  {self._esc(bullet)}", styles["bullet"]))
			if links:
				flowables.append(Paragraph(self._link_markup("  |  ".join(links)), styles["link"]))
		return flowables

	def _education_flowables(self, lines: list[str], styles: dict, width: float) -> list:
		flowables = []
		blocks: list[list[str]] = []
		current: list[str] = []
		for line in lines:
			_, date = self._split_date(line)
			starts_school = bool(date) and not self._GPA.search(line) and not self._BULLET.match(line)
			if starts_school and current:
				blocks.append(current)
				current = [line]
			else:
				current.append(line)
		if current:
			blocks.append(current)

		for block in blocks:
			first, *rest = block
			school, degree, date, gpa = self._split_education_line(first)
			if not school and degree:
				school, degree = degree, ""
			if school:
				flowables.append(self._lr(
					f"<b>{self._esc(school)}</b>",
					self._esc(date),
					styles["title"],
					styles["right"],
					width,
				))
			if degree or gpa:
				flowables.append(self._lr(
					self._esc(degree),
					self._esc(gpa),
					styles["body"],
					styles["right"],
					width,
				))
			for line in rest:
				if self._BULLET.match(line):
					flowables.append(Paragraph(
						f"•  {self._esc(self._BULLET.sub('', line).strip())}",
						styles["bullet"],
					))
					continue
				left, _, extra_date, extra_gpa = self._split_education_line(line)
				right = extra_gpa or extra_date
				text = left or line
				if right:
					flowables.append(self._lr(self._esc(text), self._esc(right), styles["body"], styles["right"], width))
				else:
					flowables.append(Paragraph(self._esc(text), styles["body"]))
		return flowables

	def _credential_flowables(self, lines: list[str], styles: dict, width: float) -> list:
		flowables = []
		for line in lines:
			text = self._BULLET.sub("", line).strip()
			view = ""
			match = re.search(r"(?:\s*[|–—-]\s*|\s+)(view)\s*$", text, flags=re.IGNORECASE)
			if match:
				view = "View"
				text = text[: match.start()].strip(" |-")
			if not text:
				continue
			if view:
				flowables.append(self._lr(
					f"•  {self._esc(text)}",
					f"<font color='#1d4ed8'>{view}</font>",
					styles["bullet"],
					styles["link"],
					width,
				))
			else:
				flowables.append(Paragraph(f"•  {self._esc(text)}", styles["bullet"]))
		return flowables

	def _split_education_line(self, line: str) -> tuple[str, str, str, str]:
		"""Return school, degree, date, and gpa from one education line."""
		text = self._BULLET.sub("", line or "").strip()
		gpa_match = self._GPA.search(text)
		gpa = re.sub(r"\s+", " ", gpa_match.group(1)).strip() if gpa_match else ""
		if gpa_match:
			text = (text[: gpa_match.start()] + text[gpa_match.end() :]).strip(" |-–,")
		parts = [part.strip(" |-") for part in text.split("|") if part.strip(" |-")]
		date = ""
		kept = []
		for part in parts or [text]:
			body, found = self._split_date(part)
			if found and not date:
				date = found
				if body:
					kept.append(body)
			elif part:
				kept.append(part if not found else body)
		school = ""
		degree = ""
		for part in kept:
			if not school and self._SCHOOL.search(part):
				school = part
			elif not degree:
				degree = part
			elif not school:
				school = part
			else:
				degree = f"{degree}, {part}"
		if not school and not degree and kept:
			degree = kept[0]
		return school, degree, date, gpa

	def _lr(self, left_html: str, right_html: str, left_style, right_style, width: float):
		if not right_html:
			return Paragraph(left_html, left_style)
		table = Table(
			[[Paragraph(left_html, left_style), Paragraph(right_html, right_style)]],
			colWidths=[width * 0.74, width * 0.26],
		)
		table.setStyle(TableStyle([
			("VALIGN", (0, 0), (-1, -1), "TOP"),
			("ALIGN", (1, 0), (1, 0), "RIGHT"),
			("LEFTPADDING", (0, 0), (-1, -1), 0),
			("RIGHTPADDING", (0, 0), (-1, -1), 0),
			("TOPPADDING", (0, 0), (-1, -1), 0),
			("BOTTOMPADDING", (0, 0), (-1, -1), 0),
		]))
		return table

	def _is_tech_line(self, line: str) -> bool:
		if self._is_link_line(line) or self._BULLET.match(line) or line.endswith((".", "!", "?")):
			return False
		return line.count(",") >= 2 and len(line.split()) <= 28

	def _is_link_line(self, line: str) -> bool:
		parts = [part.strip(" .") for part in re.split(r"\s*\|\s*", line.strip()) if part.strip()]
		if not parts or len(line) > 90:
			return False
		return all(self._LINK_TOKEN.match(part) for part in parts)

	def _link_markup(self, text: str) -> str:
		parts = [part.strip() for part in re.split(r"\s*\|\s*", text) if part.strip()]
		return "  |  ".join(f"<font color='#1d4ed8'>{self._esc(part)}</font>" for part in parts)

	def _group_entries(self, lines: list[str]) -> list[dict]:
		entries = []
		current = {"title": "", "meta": [], "bullets": [], "links": []}
		for line in lines:
			if self._is_link_line(line):
				current["links"].append(line)
				continue
			if self._BULLET.match(line):
				current["bullets"].append(self._BULLET.sub("", line).strip())
				continue
			if current["bullets"] or current["links"]:
				entries.append(current)
				current = {"title": line, "meta": [], "bullets": [], "links": []}
			elif not current["title"]:
				current["title"] = line
			else:
				current["meta"].append(line)
		if current["title"] or current["meta"] or current["bullets"] or current["links"]:
			entries.append(current)
		return entries

	def _split_date(self, title: str) -> tuple[str, str]:
		match = self._DATE.search(title or "")
		if not match:
			return title, ""
		date = re.sub(r"\s*[\u2013\u2014\-]\s*", " – ", match.group(1))
		date = re.sub(r"\s+", " ", date).strip()
		rest = (title[: match.start()] + title[match.end() :]).strip(" |-–—")
		return rest, date

	def _skill_markup(self, line: str) -> str:
		if ":" in line:
			label, _, rest = line.partition(":")
			if 0 < len(label) <= 32:
				return f"<b>{self._esc(label)}:</b> {self._esc(rest.strip())}"
		return self._esc(line)

	def _esc(self, text: str) -> str:
		return html.escape(text or "", quote=False)
