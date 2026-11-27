import json, re, os, shutil

def make_code(source):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source}

def md(lines):
    return {"cell_type": "markdown", "metadata": {}, "source": lines}

cells = []

# Cell 0 - Header
cells.append(md([
    "# Resume Optimizer -- Inference Only",
    "",
    "Loads your trained V6 LoRA adapter and generates optimized resumes with ATS scoring.",
    "**Steps:** Mount Drive -> Upload adapter zip (if not on Drive) -> Run all -> Get PDF + ATS score",
    "",
    "**Features:**",
    "- Multi-pass generation (3 tries, picks best ATS score)",
    "- ATS keyword matching score + coverage report",
    "- **Extracts and preserves LinkedIn, GitHub, portfolio, and other profile links**",
    "- Section-by-section quality check",
    "- PDF + TXT + JSON metadata export to Drive"
]))

# Cell 1 - Install
cells.append(make_code(
    'import subprocess, sys\n'
    'subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",\n'
    '    "transformers>=4.51.0", "peft", "bitsandbytes", "accelerate", "reportlab"])\n'
    'print("Dependencies ready")'
))

# Cell 2 - GPU
cells.append(make_code(
    'import os, re, gc, json, zipfile\n'
    'from pathlib import Path\n'
    'from datetime import datetime\n'
    'from google.colab import drive, files\n'
    'import torch\n'
    'if not torch.cuda.is_available():\n'
    '    raise RuntimeError("Set Runtime -> Change runtime type -> T4 GPU")\n'
    'print("GPU:", torch.cuda.get_device_name(0))'
))

# Cell 3 - Mount Drive
cells.append(make_code(
    'drive.mount("/content/drive", force_remount=False)\n'
    'PROJECT = Path("/content/drive/MyDrive/ResumeOptimizer")\n'
    'ADAPTER_DIR = PROJECT / "adapters" / "ResumeOptimizer-LoRA-v6"\n'
    'for d in [PROJECT, PROJECT/"adapters", PROJECT/"outputs"]:\n'
    '    d.mkdir(parents=True, exist_ok=True)\n'
    'print("Adapter path:", ADAPTER_DIR)\n'
    'print("Adapter exists:", ADAPTER_DIR.exists())'
))

# Cell 4 - Upload adapter
cells.append(make_code(
    'if not (ADAPTER_DIR / "adapter_model.safetensors").exists():\n'
    '    print("Adapter zip not found. Upload the zip from training.")\n'
    '    uploaded = files.upload()\n'
    '    zip_path = list(uploaded.keys())[0]\n'
    '    with zipfile.ZipFile(zip_path) as z:\n'
    '        z.extractall(ADAPTER_DIR)\n'
    '    print("Extracted to:", ADAPTER_DIR)\n'
    'else:\n'
    '    print("Using adapter from Drive.")\n'
    'for p in sorted(ADAPTER_DIR.iterdir()):\n'
    '    print(" ", p.name)'
))

# Cell 5 - Load model
cells.append(make_code(
    'from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig\n'
    'from peft import PeftModel\n'
    'BASE_MODEL_NAME = "/"\n'
    'print("Loading tokenizer...")\n'
    'tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, trust_remote_code=True)\n'
    'if tokenizer.pad_token is None:\n'
    '    tokenizer.pad_token = tokenizer.eos_token\n'
    'tokenizer.padding_side = "left"\n'
    'print("Loading base model in 4-bit (~2 min)...")\n'
    'bnb_config = BitsAndBytesConfig(\n'
    '    load_in_4bit=True,\n'
    '    bnb_4bit_quant_type="nf4",\n'
    '    bnb_4bit_use_double_quant=True,\n'
    '    bnb_4bit_compute_dtype=torch.float16,\n'
    ')\n'
    'base_model = AutoModelForCausalLM.from_pretrained(\n'
    '    BASE_MODEL_NAME,\n'
    '    quantization_config=bnb_config,\n'
    '    device_map="auto",\n'
    '    trust_remote_code=True,\n'
    '    torch_dtype=torch.float16,\n'
    ')\n'
    'print("Loading LoRA adapter...")\n'
    'model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))\n'
    'model.eval()\n'
    'print("Model ready!")'
))

# Cell 6 - Prompt + Link extractor
prompt_code = (
    'MASTER_SYSTEM = """You are an elite AI Resume Optimizer for top-tier tech companies.\n'
    '\n'
    '# NON-NEGOTIABLE RULES\n'
    '- NEVER return the resume unchanged. Always rewrite.\n'
    '- NEVER invent employers, job titles, dates, degrees, certifications, or numbers.\n'
    '- NEVER add a SOFT SKILLS section unless the original has one.\n'
    '- NEVER output reasoning, commentary, or "Here is your optimized resume".\n'
    '- NEVER use phrases like "leveraging", "utilizing", "harnessing" after bullets.\n'
    '- NEVER print a title line that says "resume".\n'
    '\n'
    '# CONTACT / LINKS (CRITICAL -- preserve all profile links)\n'
    '- Extract ALL links from the original resume: LinkedIn, GitHub, portfolio, personal website, Kaggle, Medium, etc.\n'
    '- Format as: Name, Phone, Email, City, State\n'
    '- Each link on its own line prefixed with the platform name, e.g.:\n'
    '    LinkedIn : linkedin.com/in/sakhita-sree-gadde-87232119a\n'
    '    GitHub   : github.com/sakhita-sree-gadde\n'
    '    Portfolio: sakhitagadde.github.io\n'
    '- Do NOT invent links. Only include links that appear in the original resume.\n'
    '- If the original has NO links, do not add any.\n'
    '- Keep the contact block at the very top, before PROFESSIONAL SUMMARY.\n'
    '\n'
    '# PROFESSIONAL SUMMARY (3-4 sentences)\n'
    '- Sentence 1: State current role/field plus years of relevant experience.\n'
    '- Sentence 2: Name 2-3 top technical strengths from the JD that the candidate already has.\n'
    '- Sentence 3: Mention a specific project or achievement demonstrating those skills.\n'
    '- Sentence 4: Express fit for this specific role and company.\n'
    '- Write in first person, no "targeting" language.\n'
    '\n'
    '# TECHNICAL SKILLS (grouped, no extra lines)\n'
    'Use ONLY these labels, only skills the resume supports:\n'
    '  Languages:\n'
    '  Core CS and Fundamentals:\n'
    '  Frontend:\n'
    '  Backend:\n'
    '  Databases:\n'
    '  AI / ML and GenAI:\n'
    '  Tools and Cloud:\n'
    '- Keep hyphenated names intact: Object-Oriented Programming, Scikit-learn, full-stack.\n'
    '- Add JD keywords to these groups ONLY if the candidate has evidence in their resume.\n'
    '- Do NOT list languages like "English" as a programming language.\n'
    '- Do NOT list "Communication", "Teamwork" under technical skills.\n'
    '\n'
    '# EXPERIENCE BULLETS (rewrite stronger)\n'
    'Start each bullet with: Built, Designed, Developed, Implemented, Led, Architected, Deployed, Optimized, Automated, Engineered, Integrated.\n'
    'Add metrics where the original had any numbers.\n'
    'Weave 1-2 JD keywords naturally into bullets where the candidate\'s work already relates.\n'
    'Keep the same employer, title, and date range.\n'
    '\n'
    '# PROJECTS\n'
    '- Rewrite descriptions to highlight technologies that match the JD.\n'
    '- Add 1-2 sentences about the tech stack and outcomes.\n'
    '\n'
    '# OTHER\n'
    '- EDUCATION: Keep as-is. Add relevant coursework if space allows.\n'
    '- CERTIFICATIONS: Keep all, format cleanly.\n'
    '- Do not pad with fluff."""\n'
    '\n'
    'import re as _re\n'
    '\n'
    'LINK_PATTERNS = {\n'
    '    "LinkedIn": r"linkedin\\.com/in/([A-Za-z0-9_-]+)",\n'
    '    "GitHub": r"github\\.com/([A-Za-z0-9_-]+)",\n'
    '    "Portfolio": r"([A-Za-z0-9_-]+\\.github\\.io(?:/[A-Za-z0-9_-]*)?)",\n'
    '    "Kaggle": r"kaggle\\.com/([A-Za-z0-9_-]+)",\n'
    '    "Medium": r"medium\\.com/@([A-Za-z0-9_-]+)",\n'
    '}\n'
    '\n'
    'def extract_links(resume_text):\n'
    '    """Pull LinkedIn, GitHub, portfolio, and other profile links from the resume."""\n'
    '    links = {}\n'
    '    for label, pat in LINK_PATTERNS.items():\n'
    '        m = _re.search(pat, resume_text, _re.IGNORECASE)\n'
    '        if m:\n'
    '            full = m.group(0)\n'
    '            if not full.startswith("http"):\n'
    '                full = "https://" + full\n'
    '            links[label] = full\n'
    '    for m in _re.finditer(r"https?://[^\\s)]+", resume_text):\n'
    '        url = m.group(0)\n'
    '        if not any(url.endswith(v.split("/")[-1]) for v in links.values()):\n'
    '            if "github" not in url.lower() and "linkedin" not in url.lower():\n'
    '                links.setdefault("Website", url)\n'
    '    return links\n'
    '\n'
    'def build_prompt(company, role, jd, resume):\n'
    '    links = extract_links(resume)\n'
    '    contact_hint = "\\n".join(["%s: %s" % (k, v) for k, v in links.items()]) if links else "No links found"\n'
    '    return "TARGET COMPANY: " + company + "\\nTARGET ROLE: " + role + "\\n\\nJOB DESCRIPTION:\\n" + jd + "\\n\\nCANDIDATE\'S ORIGINAL RESUME:\\n" + resume + "\\n\\nEXTRACTED LINKS (must include these in the contact block):\\n" + contact_hint + "\\n\\nRewrite the complete resume. Preserve ALL extracted links in the contact block. Strengthen every section. Add JD keywords naturally where the candidate has evidence. Output ONLY the resume text."\n'
    '\n'
    'def apply_chat(messages, add_gen=True):\n'
    '    try:\n'
    '        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen, enable_thinking=False)\n'
    '    except TypeError:\n'
    '        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen)\n'
    '\n'
    'def generate(company, role, jd, resume, temperature=0.6, top_p=0.93, max_new=1200):\n'
    '    messages = [\n'
    '        {"role": "system", "content": MASTER_SYSTEM},\n'
    '        {"role": "user", "content": build_prompt(company, role, jd, resume)},\n'
    '    ]\n'
    '    formatted = apply_chat(messages)\n'
    '    inputs = tokenizer(formatted, return_tensors="pt").to(model.device)\n'
    '    with torch.no_grad():\n'
    '        out = model.generate(\n'
    '            **inputs,\n'
    '            max_new_tokens=max_new,\n'
    '            temperature=temperature,\n'
    '            top_p=top_p,\n'
    '            do_sample=True,\n'
    '            pad_token_id=tokenizer.eos_token_id,\n'
    '            repetition_penalty=1.08,\n'
    '        )\n'
    '    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()\n'
    '\n'
    'print("Prompts + link extractor ready")'
)
cells.append(make_code(prompt_code))

# Cell 7 - ATS Scorer with link check
ats_code = r'''SECTION_NAMES = {
    "PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "SOFT SKILLS",
    "PROFESSIONAL EXPERIENCE", "INTERNSHIP EXPERIENCE",
    "PROJECTS", "EDUCATION", "CERTIFICATIONS", "ACHIEVEMENTS",
    "CONTACT"
}

LINK_PATTERNS = {
    "LinkedIn": r"linkedin\.com/in/[A-Za-z0-9_-]+",
    "GitHub": r"github\.com/[A-Za-z0-9_-]+",
    "Portfolio": r"[A-Za-z0-9_-]+\.github\.io",
    "Kaggle": r"kaggle\.com/[A-Za-z0-9_-]+",
    "Website": r"https?://[^\s)]+",
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

def ats_score(optimized_text, jd_text, original_links=None):
    keywords = extract_keywords(jd_text)
    sections = parse_resume_sections(optimized_text)
    full_text = " ".join(str(v) for v in sections.values()).lower()
    matched = [kw for kw in keywords if kw in full_text]
    missing = [kw for kw in keywords if kw not in full_text]
    coverage = len(matched) / len(keywords) * 100 if keywords else 0
    required = {"PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE", "EDUCATION"}
    present = required & set(sections.keys())
    section_bonus = len(present) / len(required) * 10
    link_score = 0
    link_report = {}
    if original_links:
        text_lower = optimized_text.lower()
        for label, url in original_links.items():
            pattern = LINK_PATTERNS.get(label, "")
            if pattern and re.search(pattern, text_lower):
                link_score += 2
                link_report[label] = "PRESERVED"
            else:
                link_report[label] = "MISSING"
    link_bonus = min(link_score, 10)
    total = min(coverage + section_bonus + link_bonus, 100)
    return {
        "ats_score": round(total, 1),
        "keyword_coverage": round(coverage, 1),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "sections_found": sorted(present),
        "sections_missing": sorted(required - present),
        "total_keywords": len(keywords),
        "link_report": link_report,
    }

def quality_report(text, original_links=None):
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
    link_flags = []
    if original_links:
        t_lower = t.lower()
        for label, url in original_links.items():
            domain = url.split("/")[2] if "://" in url else url.split("/")[0]
            if domain.lower() not in t_lower:
                link_flags.append("MISSING_LINK: %s (%s)" % (label, url))
    if link_flags:
        flags.extend(link_flags)
    if not flags:
        flags.append("OK")
    return {"quality_flags": flags, "sections_found": sorted(found), "char_count": len(t)}

print("ATS scorer with link detection ready")
'''
cells.append(make_code(ats_code))

# Cell 8 - Multi-pass optimizer
mp_code = (
    'def multi_pass_optimize(company, role, jd, resume, n_passes=3,\n'
    '                           temperatures=[0.55, 0.65, 0.5]):\n'
    '    original_links = extract_links(resume)\n'
    '\n'
    '    best_text = None\n'
    '    best_score = -1\n'
    '    best_ats = None\n'
    '    best_qual = None\n'
    '\n'
    '    for i in range(n_passes):\n'
    '        temp = temperatures[i % len(temperatures)]\n'
    '        raw = generate(company, role, jd, resume, temperature=temp)\n'
    '        ats = ats_score(raw, jd, original_links=original_links)\n'
    '        qual = quality_report(raw, original_links=original_links)\n'
    '\n'
    '        print("\\n--- Pass %d (temp=%.2f) ---" % (i+1, temp))\n'
    '        print("  ATS Score   : %s%%  (%s%% keyword coverage)" % (ats["ats_score"], ats["keyword_coverage"]))\n'
    '        if ats.get("link_report"):\n'
    '            for label, status in ats["link_report"].items():\n'
    '                print("  Link %s: %s" % (label, status))\n'
    '        print("  Quality     : %s" % qual["quality_flags"])\n'
    '        print("  Sections    : %s" % qual["sections_found"])\n'
    '        print("  Length      : %s chars" % qual["char_count"])\n'
    '\n'
    '        if ats["ats_score"] > best_score:\n'
    '            best_score = ats["ats_score"]\n'
    '            best_text = raw\n'
    '            best_ats = ats\n'
    '            best_qual = qual\n'
    '            print("  >>> NEW BEST (score: %s%%)" % best_score)\n'
    '\n'
    '    return best_text, best_ats, best_qual\n'
    '\n'
    'def optimize(company, role, jd, resume):\n'
    '    text, ats, qual = multi_pass_optimize(company, role, jd, resume)\n'
    '    return text, ats, qual\n'
    '\n'
    'print("Multi-pass optimizer ready")'
)
cells.append(make_code(mp_code))

# Cell 9 - PDF Saver
pdf_code = r'''from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
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
                     "PROJECTS","EDUCATION","CERTIFICATIONS","ACHIEVEMENTS","CONTACT"}
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
    link_style = ParagraphStyle("Link", fontName="Helvetica-Oblique", fontSize=9,
                                 leading=12, leftIndent=12, textColor="#1a0dab", spaceAfter=1)
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    elements = []
    first = True
    section_names = {"PROFESSIONAL SUMMARY","TECHNICAL SKILLS","SOFT SKILLS",
                     "PROFESSIONAL EXPERIENCE","INTERNSHIP EXPERIENCE",
                     "PROJECTS","EDUCATION","CERTIFICATIONS","ACHIEVEMENTS","CONTACT"}
    for line in cleaned.splitlines():
        s = line.strip()
        if not s:
            elements.append(Spacer(1, 2))
            continue
        upper = s.upper().rstrip(":")
        if first and upper not in section_names and "@" not in s and "|" not in s and ":" not in s:
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
        if re.match(r"^(LinkedIn|GitHub|Portfolio|Website|Kaggle|Medium)\s*:", s, re.IGNORECASE):
            elements.append(Paragraph(s.replace("&", "&amp;").replace("<", "&lt;"), link_style))
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
cells.append(make_code(pdf_code))

# Cell 10 - Main run cell with your actual resume
main_code = (
    '# --- RUN: Edit your resume and JD below ---\n'
    '\n'
    'RESUME_INPUT = """Sakhita Sree Gadde\n'
    '(979) 344-8061 | sakhitasreerg2000@gmail.com | Bryan, TX\n'
    'linkedin.com/in/sakhita-sree-gadde-87232119a\n'
    'github.com/sakhita-sree-gadde\n'
    'sakhitagadde.github.io\n'
    '\n'
    'PROFESSIONAL SUMMARY\n'
    'Data Science professional with Kubernetes-based orchestration experience and proficiency in machine learning, Generative AI, and ETL/ELT pipeline development. Skilled in agile methodologies and implementing CI/CD pipelines for production environments. Strong background in ML engineering, advanced data analytics, and LLM-based model serving with PEFT methods.\n'
    '\n'
    'TECHNICAL SKILLS\n'
    'Languages: Python, SQL, C++, Java, JavaScript\n'
    'Core CS: Data Structures and Algorithms, Object-Oriented Programming\n'
    'Frontend: React.js, HTML, CSS\n'
    'Backend: REST APIs, FastAPI, Flask, Spring Boot, Node.js\n'
    'Databases: DynamoDB, MySQL\n'
    'AI / ML and GenAI: Pandas, Scikit-learn, Gemini API, LangChain, PyTorch, TensorFlow, Keras, Hugging Face, OpenCV\n'
    'Tools and Cloud: Git, Docker, Kubernetes\n'
    '\n'
    'SOFT SKILLS\n'
    'Communication, Problem-Solving, Teamwork\n'
    '\n'
    'PROFESSIONAL EXPERIENCE\n'
    'Software Engineer | Infosys LTD | Jul 2022 - Dec 2023\n'
    '- Built and deployed ML-powered applications using Python, TensorFlow, and Keras\n'
    '- Automated CI/CD pipelines with Docker and Kubernetes, reducing deployment time by 30 percent\n'
    '- Developed ETL/ELT pipelines processing large-scale datasets with SQL and Pandas\n'
    '- Integrated LLM-based services using Hugging Face and LangChain for production inference\n'
    '- Collaborated with cross-functional teams using Agile sprints to deliver machine learning solutions\n'
    '\n'
    'PROJECTS\n'
    'AI Resume Optimizer\n'
    '- Built a full-stack web application with React frontend and FastAPI backend\n'
    '- Integrated LLM-based resume optimization using fine-tuned model\n'
    '- Deployed with Docker containers and Kubernetes orchestration\n'
    '\n'
    'Food Spoilage Detection System\n'
    '- Developed a CNN-based image classification model with OpenCV for real-time detection\n'
    '- Applied K-Means clustering for feature extraction and pattern analysis\n'
    '- Published results at ICCNCT-2020 with Springer\n'
    '\n'
    'EDUCATION\n'
    'Master of Science in Data Science (Computer Science), Texas A and M University, College Station, Texas, Dec 2023\n'
    'Bachelor of Technology in Electronics and Communication Engineering, Amrita Vishwa Vidyapeetham, Kollam, India, Jun 2021\n'
    '\n'
    'CERTIFICATIONS\n'
    'Certified Kubernetes Administrator\n'
    'DNA Rise Award - Engineering Excellence, Infosys LTD\n'
    'Bronze Certificate from DST-TI competition 2019 (ICCDC)"""\n'
    '\n'
    'COMPANY = "Amazon"\n'
    'ROLE = "Software Development Engineer"\n'
    'JD = """We are looking for a Software Development Engineer with strong programming skills in Python, Java, or C++. You will design and build scalable distributed systems using microservices and REST APIs. Experience with cloud platforms (AWS), containerization (Docker, Kubernetes), and CI/CD pipelines is required. Strong knowledge of data structures, algorithms, SQL databases, and Git. Problem-solving and Agile teamwork skills. Experience with machine learning, LLMs, NLP, or generative AI is a strong plus."""\n'
    '\n'
    'print("=" * 70)\n'
    'print("OPTIMIZING RESUME")\n'
    'print("=" * 70)\n'
    '\n'
    'optimized_text, ats_result, quality_result = optimize(COMPANY, ROLE, JD, RESUME_INPUT)\n'
    '\n'
    'print("\\n" + "=" * 70)\n'
    'print("BEST OPTIMIZED RESUME")\n'
    'print("=" * 70)\n'
    'print(optimized_text)\n'
    '\n'
    'print("\\n" + "=" * 70)\n'
    'print("ATS ANALYSIS")\n'
    'print("=" * 70)\n'
    'print("  Overall ATS Score : %s%%" % ats_result["ats_score"])\n'
    'print("  Keyword Coverage  : %s%%" % ats_result["keyword_coverage"])\n'
    'print("  Matched keywords  : %s" % ats_result["matched_keywords"])\n'
    'print("  Missing keywords  : %s" % ats_result["missing_keywords"])\n'
    'if ats_result.get("link_report"):\n'
    '    print("  Link preservation:")\n'
    '    for label, status in ats_result["link_report"].items():\n'
    '        print("    %s: %s" % (label, status))\n'
    'print("  Quality flags     : %s" % quality_result["quality_flags"])\n'
    '\n'
    'save_resume(optimized_text, COMPANY, ats_result, quality_result)'
)
cells.append(make_code(main_code))

# Cell 11 - Helper
cells.append(make_code(
    '# Quick helper: one-liner for any resume\n'
    'def quick_optimize(company, role, jd_text, resume_text):\n'
    '    text, ats, _ = optimize(company, role, jd_text, resume_text)\n'
    '    _, pdf, _ = save_resume(text, company, ats, {})\n'
    '    return text, ats, pdf\n'
    '\n'
    'print(\'Usage: quick_optimize("Amazon", "SDE", jd_text, resume_text)\')\n'
    'print(\'Returns: (optimized_text, ats_dict, pdf_path)\')'
))

# Cell 12 - Memory cleanup
cells.append(make_code(
    'import gc, torch\n'
    'del base_model\n'
    'del model\n'
    'gc.collect()\n'
    'torch.cuda.empty_cache()\n'
    'print("Memory cleared")'
))

# Build
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

out = '/sessions/exciting-loving-edison/mnt/ai_resume_jh/ResumeOptimizer_Inference.ipynb'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

dst = '/sessions/exciting-loving-edison/mnt/outputs/ResumeOptimizer_Inference.ipynb'
shutil.copy(out, dst)
print("Saved %d cells, %.1f KB" % (len(cells), os.path.getsize(out)/1024))
