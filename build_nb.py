import json

def make_code(source):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source}

def md(lines):
    return {"cell_type": "markdown", "metadata": {}, "source": lines}

cells = []

cells.append(md([
    "# Resume Optimizer -- Inference Only",
    "",
    "Loads your trained V6 LoRA adapter and generates optimized resumes with ATS scoring.",
    "**Steps:** Mount Drive -> Upload adapter zip (if not on Drive) -> Run all -> Get PDF + ATS score",
    "",
    "**Features:**",
    "- Multi-pass generation (3 tries, picks best ATS score)",
    "- ATS keyword matching score + coverage report",
    "- Section-by-section quality check",
    "- PDF + TXT + JSON metadata export to Drive"
]))

cells.append(make_code("import subprocess, sys\nsubprocess.check_call([sys.executable, \"-m\", \"pip\", \"install\", \"-q\",\n    \"transformers>=4.51.0\", \"peft\", \"bitsandbytes\", \"accelerate\", \"reportlab\"])\nprint(\"Dependencies ready\")"))

cells.append(make_code("import os, re, gc, json, zipfile\nfrom pathlib import Path\nfrom datetime import datetime\nfrom google.colab import drive, files\nimport torch\nif not torch.cuda.is_available():\n    raise RuntimeError(\"Set Runtime -> Change runtime type -> T4 GPU\")\nprint(\"GPU:\", torch.cuda.get_device_name(0))"))

cells.append(make_code("drive.mount(\"/content/drive\", force_remount=False)\nPROJECT = Path(\"/content/drive/MyDrive/ResumeOptimizer\")\nADAPTER_DIR = PROJECT / \"adapters\" / \"ResumeOptimizer-LoRA-v6\"\nfor d in [PROJECT, PROJECT/\"adapters\", PROJECT/\"outputs\"]:\n    d.mkdir(parents=True, exist_ok=True)\nprint(\"Adapter path:\", ADAPTER_DIR)\nprint(\"Adapter exists:\", ADAPTER_DIR.exists())"))

cells.append(make_code("if not (ADAPTER_DIR / \"adapter_model.safetensors\").exists():\n    print(\"Adapter zip not found. Upload the zip from training.\")\n    uploaded = files.upload()\n    zip_path = list(uploaded.keys())[0]\n    with zipfile.ZipFile(zip_path) as z:\n        z.extractall(ADAPTER_DIR)\n    print(\"Extracted to:\", ADAPTER_DIR)\nelse:\n    print(\"Using adapter from Drive.\")\nfor p in sorted(ADAPTER_DIR.iterdir()):\n    print(\" \", p.name)"))

cells.append(make_code("from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig\nfrom peft import PeftModel\nBASE_MODEL_NAME = \"/\"\nprint(\"Loading tokenizer...\")\ntokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, trust_remote_code=True)\nif tokenizer.pad_token is None:\n    tokenizer.pad_token = tokenizer.eos_token\ntokenizer.padding_side = \"left\"\nprint(\"Loading base model in 4-bit (~2 min)...\")\nbnb_config = BitsAndBytesConfig(\n    load_in_4bit=True,\n    bnb_4bit_quant_type=\"nf4\",\n    bnb_4bit_use_double_quant=True,\n    bnb_4bit_compute_dtype=torch.float16,\n)\nbase_model = AutoModelForCausalLM.from_pretrained(\n    BASE_MODEL_NAME,\n    quantization_config=bnb_config,\n    device_map=\"auto\",\n    trust_remote_code=True,\n    torch_dtype=torch.float16,\n)\nprint(\"Loading LoRA adapter...\")\nmodel = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))\nmodel.eval()\nprint(\"Model ready!\")"))

MASTER_SYSTEM = """You are an elite AI Resume Optimizer for top-tier tech companies.

# NON-NEGOTIABLE RULES
- NEVER return the resume unchanged. Always rewrite.
- NEVER invent employers, job titles, dates, degrees, certifications, or numbers.
- NEVER add a SOFT SKILLS section unless the original has one.
- NEVER output reasoning, commentary, or "Here is your optimized resume".
- NEVER use phrases like "leveraging", "utilizing", "harnessing" after bullets.
- NEVER print a title line that says "resume".

# PROFESSIONAL SUMMARY (3-4 sentences)
- Sentence 1: State current role/field plus years of relevant experience.
- Sentence 2: Name 2-3 top technical strengths from the JD that the candidate already has.
- Sentence 3: Mention a specific project or achievement demonstrating those skills.
- Sentence 4: Express fit for this specific role and company.
- Write in first person, no "targeting" language.

# TECHNICAL SKILLS (grouped, no extra lines)
Use ONLY these labels, only skills the resume supports:
  Languages:
  Core CS and Fundamentals:
  Frontend:
  Backend:
  Databases:
  AI / ML and GenAI:
  Tools and Cloud:
- Keep hyphenated names intact: Object-Oriented Programming, Scikit-learn, full-stack.
- Add JD keywords to these groups ONLY if the candidate has evidence in their resume.
- Do not dump every JD keyword as a skill.

# EXPERIENCE BULLETS (rewrite stronger)
Start each bullet with: Built, Designed, Developed, Implemented, Led, Architected, Deployed, Optimized, Automated, Engineered, Integrated.
Add metrics where the original had any numbers.
Weave 1-2 JD keywords naturally into bullets where the candidate's work already relates.
Keep the same employer, title, and date range.

# PROJECTS
- Rewrite descriptions to highlight technologies that match the JD.
- Add 1-2 sentences about the tech stack and outcomes.

# OTHER
- EDUCATION: Keep as-is. Add relevant coursework if space allows.
- CERTIFICATIONS: Keep all, format cleanly.
- Do not pad with fluff."""

prompt_source = 'MASTER_SYSTEM = """' + MASTER_SYSTEM + '"""\n\n\ndef build_prompt(company, role, jd, resume):\n    return f"TARGET COMPANY: {company}\\nTARGET ROLE: {role}\\n\\nJOB DESCRIPTION:\\n{jd}\\n\\nCANDIDATE\'S ORIGINAL RESUME:\\n{resume}\\n\\nRewrite the complete resume. Strengthen every section. Add JD keywords naturally where the candidate has evidence. Output ONLY the resume text."\n\n\ndef apply_chat(messages, add_gen=True):\n    try:\n        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen, enable_thinking=False)\n    except TypeError:\n        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen)\n\n\ndef generate(company, role, jd, resume, temperature=0.55, top_p=0.93, max_new=1000):\n    messages = [\n        {"role": "system", "content": MASTER_SYSTEM},\n        {"role": "user", "content": build_prompt(company, role, jd, resume)},\n    ]\n    formatted = apply_chat(messages)\n    inputs = tokenizer(formatted, return_tensors="pt").to(model.device)\n    with torch.no_grad():\n        out = model.generate(\n            **inputs,\n            max_new_tokens=max_new,\n            temperature=temperature,\n            top_p=top_p,\n            do_sample=True,\n            pad_token_id=tokenizer.eos_token_id,\n            repetition_penalty=1.08,\n        )\n    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()\n\n\nprint("Prompts loaded")'

cells.append(make_code(prompt_source))

ats_source = r'''SECTION_NAMES = {
    "PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "SOFT SKILLS",
    "PROFESSIONAL EXPERIENCE", "INTERNSHIP EXPERIENCE",
    "PROJECTS", "EDUCATION", "CERTIFICATIONS", "ACHIEVEMENTS"
}

def parse_resume_sections(text):
    sections = {}
    current = "HEADER"
    for line in text.splitlines():
        upper = line.strip().upper().rstrip(":")
        if upper in SECTION_NAMES:
            current = upper
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections

def extract_keywords(jd_text):
    stop = {"the","and","or","for","to","in","on","with","a","an","of","at","by",
            "from","is","are","was","were","be","been","being","have","has","had",
            "do","does","did","will","would","shall","should","may","might","can",
            "could","must","that","this","these","those","it","its","you","your",
            "our","we","they","them","their","us","not","no","nor","but","if",
            "then","than","too","very","just","about","above","after","again",
            "all","also","as","because","before","between","both","during","each",
            "few","further","here","how","into","more","most","other","out","over",
            "own","same","so","some","such","up","what","when","where","which",
            "while","who","whom","why","down","off","only","once"}
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]+", jd_text.lower())
    return [w for w in words if w not in stop and len(w) > 2]

def ats_score(optimized_text, jd_text):
    keywords = extract_keywords(jd_text)
    sections = parse_resume_sections(optimized_text)
    full_text = " ".join(str(v) for v in sections.values()).lower()
    matched = [kw for kw in keywords if kw in full_text]
    missing = [kw for kw in keywords if kw not in full_text]
    coverage = len(matched) / len(keywords) * 100 if keywords else 0
    required = {"PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE", "EDUCATION"}
    present = required & set(sections.keys())
    section_bonus = len(present) / len(required) * 10
    total = min(coverage + section_bonus, 100)
    return {
        "ats_score": round(total, 1),
        "keyword_coverage": round(coverage, 1),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "sections_found": sorted(present),
        "sections_missing": sorted(required - present),
        "total_keywords": len(keywords),
    }

def quality_report(text):
    flags = []
    t = text.strip()
    if len(t) < 200:
        flags.append("TOO_SHORT")
    found = set()
    for line in t.splitlines():
        if line.strip().upper().rstrip(":") in SECTION_NAMES:
            found.add(line.strip().upper().rstrip(":"))
    if "PROFESSIONAL SUMMARY" not in found:
        flags.append("MISSING_SUMMARY")
    if "TECHNICAL SKILLS" not in found:
        flags.append("MISSING_SKILLS")
    if not any(s in found for s in ["PROFESSIONAL EXPERIENCE", "INTERNSHIP EXPERIENCE"]):
        flags.append("MISSING_EXPERIENCE")
    for phrase in ["leveraging", "utilizing", "harnessing", "responsible for"]:
        if phrase.lower() in t.lower():
            flags.append("LAZY_PHRASE: '%s'" % phrase)
    if not flags:
        flags.append("OK")
    return {"quality_flags": flags, "sections_found": sorted(found), "char_count": len(t)}

print("ATS scorer ready")
'''

cells.append(make_code(ats_source))

mp_source = r'''def multi_pass_optimize(company, role, jd, resume, n_passes=3,
                           temperatures=[0.5, 0.6, 0.55]):
    best_text = None
    best_score = -1
    best_ats = None
    best_qual = None
    for i in range(n_passes):
        temp = temperatures[i % len(temperatures)]
        raw = generate(company, role, jd, resume, temperature=temp)
        ats = ats_score(raw, jd)
        qual = quality_report(raw)
        print("\n--- Pass %d (temp=%.2f) ---" % (i+1, temp))
        print("  ATS Score   : %s%%  (%s%% keyword coverage)" % (ats["ats_score"], ats["keyword_coverage"]))
        print("  Quality     : %s" % qual["quality_flags"])
        print("  Sections    : %s" % qual["sections_found"])
        print("  Length      : %s chars" % qual["char_count"])
        if ats["ats_score"] > best_score:
            best_score = ats["ats_score"]
            best_text = raw
            best_ats = ats
            best_qual = qual
            print("  >>> NEW BEST (score: %s%%)" % best_score)
    return best_text, best_ats, best_qual

def optimize(company, role, jd, resume):
    text, ats, qual = multi_pass_optimize(company, role, jd, resume)
    return text, ats, qual

print("Multi-pass optimizer ready")
'''

cells.append(make_code(mp_source))

pdf_source = r'''from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

def clean_for_pdf(text):
    out = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            out.append("")
            continue
        upper = line.strip().upper().rstrip(":")
        sections = {"PROFESSIONAL SUMMARY","TECHNICAL SKILLS","SOFT SKILLS",
                     "PROFESSIONAL EXPERIENCE","INTERNSHIP EXPERIENCE",
                     "PROJECTS","EDUCATION","CERTIFICATIONS","ACHIEVEMENTS"}
        if upper in sections:
            out.append("")
            out.append(line.upper())
            out.append("")
        else:
            out.append(line)
    return "\n".join(out).replace("\n\n\n", "\n\n")

def save_pdf(text, output_path):
    cleaned = clean_for_pdf(text)
    name_style = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=16, spaceAfter=4)
    sec_style = ParagraphStyle("Sec", fontName="Helvetica-Bold", fontSize=11,
                                spaceBefore=8, spaceAfter=2, textColor="#1a1a2e")
    body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=13, spaceAfter=2)
    bullet_style = ParagraphStyle("Bullet", fontName="Helvetica", fontSize=10, leading=13,
                                   leftIndent=12, spaceAfter=2)
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    elements = []
    first = True
    section_names = {"PROFESSIONAL SUMMARY","TECHNICAL SKILLS","SOFT SKILLS",
                     "PROFESSIONAL EXPERIENCE","INTERNSHIP EXPERIENCE",
                     "PROJECTS","EDUCATION","CERTIFICATIONS","ACHIEVEMENTS"}
    for line in cleaned.splitlines():
        s = line.strip()
        if not s:
            elements.append(Spacer(1, 2))
            continue
        upper = s.upper().rstrip(":")
        if first and upper not in section_names and "@" not in s and "|" not in s:
            elements.append(Paragraph(s.replace("&", "&amp;").replace("<", "&lt;"), name_style))
            first = False
            continue
        first = False
        if upper in section_names:
            elements.append(Paragraph(s.upper(), sec_style))
            continue
        if s.startswith(("\u2022","-","*")):
            content = s.lstrip("\u2022-* ").strip()
            elements.append(Paragraph("• " + content.replace("&", "&amp;").replace("<", "&lt;"), bullet_style))
            continue
        elements.append(Paragraph(s.replace("&", "&amp;").replace("<", "&lt;"), body_style))
    doc.build(elements)
    return output_path

def save_resume(text, company, ats, qual):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', company)[:25]
    out_dir = PROJECT / "outputs" / safe
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / ("resume_" + ts + ".txt")
    pdf_path = out_dir / ("resume_" + ts + ".pdf")
    meta_path = out_dir / ("resume_" + ts + "_ats.json")
    txt_path.write_text(text, encoding="utf-8")
    save_pdf(text, pdf_path)
    meta_path.write_text(json.dumps({"ats": ats, "quality": qual}, indent=2), encoding="utf-8")
    print("\nSaved files:")
    print("  TXT : %s" % txt_path)
    print("  PDF : %s" % pdf_path)
    print("  ATS : %s" % meta_path)
    return txt_path, pdf_path, meta_path

print("Saver ready")
'''

cells.append(make_code(pdf_source))

main_source = r'''# --- RUN: Edit your resume and JD below ---

RESUME_INPUT = """Kiran Patel
kiran.patel@email.com | +91-9876543210 | Hyderabad, India

PROFESSIONAL SUMMARY
Computer Science student with experience in full-stack development and machine learning.

TECHNICAL SKILLS
Languages: Python, Java, JavaScript, HTML, CSS
Frontend: React.js, HTML, CSS
Backend: FastAPI, Flask, Spring Boot
Databases: MySQL, DynamoDB
AI / ML: Scikit-learn, TensorFlow, Keras
Tools: Git, Docker, Kubernetes

PROFESSIONAL EXPERIENCE
Software Engineer Intern | NovaApps | Jun 2024 - Aug 2024
- Built Python APIs and automation scripts
- Collaborated with team of 5 on CI/CD pipeline

PROJECTS
AI Resume Optimizer
- Built a full-stack app with React and FastAPI
- Integrated LLM-based resume optimization

EDUCATION
B.E. Computer Science, Anurag University, 2023 - 2027"""

COMPANY = "Amazon"
ROLE = "Software Development Engineer"
JD = """We are looking for a Software Development Engineer with strong programming skills in Python, Java, or C++. You will design and build scalable distributed systems using microservices and REST APIs. Experience with cloud platforms (AWS), containerization (Docker, Kubernetes), and CI/CD pipelines is required. Strong knowledge of data structures, algorithms, SQL databases, and Git. Problem-solving and Agile teamwork skills. Experience with machine learning, LLMs, NLP, or generative AI is a plus."""

print("=" * 70)
print("OPTIMIZING RESUME")
print("=" * 70)

optimized_text, ats_result, quality_result = optimize(COMPANY, ROLE, JD, RESUME_INPUT)

print("\n" + "=" * 70)
print("BEST OPTIMIZED RESUME")
print("=" * 70)
print(optimized_text)

print("\n" + "=" * 70)
print("ATS ANALYSIS")
print("=" * 70)
print("  Overall ATS Score : %s%%" % ats_result["ats_score"])
print("  Keyword Coverage  : %s%%" % ats_result["keyword_coverage"])
print("  Matched keywords  : %s" % ats_result["matched_keywords"])
print("  Missing keywords  : %s" % ats_result["missing_keywords"])
print("  Quality flags     : %s" % quality_result["quality_flags"])

save_resume(optimized_text, COMPANY, ats_result, quality_result)
'''

cells.append(make_code(main_source))

cells.append(make_code('# Quick helper: one-liner for any resume\ndef quick_optimize(company, role, jd_text, resume_text):\n    text, ats, _ = optimize(company, role, jd_text, resume_text)\n    _, pdf, _ = save_resume(text, company, ats, {})\n    return text, ats, pdf\n\nprint(\'Usage: quick_optimize("Amazon", "SDE", jd_text, resume_text)\')\nprint(\'Returns: (optimized_text, ats_dict, pdf_path)\')'))

cells.append(make_code("import gc, torch\ndel base_model\ndel model\ngc.collect()\ntorch.cuda.empty_cache()\nprint(\"Memory cleared\")"))

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"gpuType": "T4", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

import os, shutil
out = '/sessions/exciting-loving-edison/mnt/ai_resume_jh/ResumeOptimizer_Inference.ipynb'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

dst = '/sessions/exciting-loving-edison/mnt/outputs/ResumeOptimizer_Inference.ipynb'
shutil.copy(out, dst)
print("Saved %d cells, %.1f KB" % (len(cells), os.path.getsize(out)/1024))
