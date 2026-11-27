import json
import os
import shutil

src = '/sessions/exciting-loving-edison/mnt/ai_resume_jh/ResumeOptimizer_Colab.ipynb'
dst = '/sessions/exciting-loving-edison/mnt/ai_resume_jh/ResumeOptimizer_Colab.ipynb.bak'
shutil.copy2(src, dst)
print("Backup saved to:", dst)

with open(src, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find V6-03d cell (cell index 8)
v6_03d_src = ''.join(nb['cells'][8]['source'])
print("Original V6-03d length:", len(v6_03d_src))

# Replace V6-03d with fixed version that does NOT auto-inject soft skills
# into existing gold examples, only keeps the teaching examples
new_03d = '''# ============================================================
# V6-03d — SOFT SKILLS COLUMN (never mix into languages/tools)
# Run after V6-03c. Extends GOLD with soft-skill separation examples.
# DOES NOT modify existing gold assistant outputs.
# ============================================================

SOFT_SKILLS_LINE = (
    "Communication, Collaboration, Problem Solving, Critical Thinking, "
    "Adaptability, Time Management, Attention to Detail, Leadership, Initiative, Ownership"
)

# NOTE: We do NOT modify existing GOLD rows here.
# The  rule "NEVER add SOFT SKILLS unless the original has one"
# must be consistent with training data. Existing gold examples that did not
# originally have SOFT SKILLS are left untouched.

GOLD.append(v6_example(
    "v6_soft_split_01",
    "Software Engineer Intern",
    "Separate technical skills from soft skills. Soft skills must not appear under languages, tools, or platforms.\\n\\nSKILLS: Java, Python, Communication, Git, Teamwork, React, Problem-Solving, MySQL, Critical Thinking, English",
    """CANDIDATE NAME
email@example.com

PROFESSIONAL SUMMARY
Computer Science student who builds applications with Java, Python, and React.

TECHNICAL SKILLS
Languages: Java, Python
Frameworks: React
Databases: MySQL
Tools: Git

SOFT SKILLS
""" + SOFT_SKILLS_LINE + """

EDUCATION
B.S. Computer Science
""",
    category="soft_skills_split",
))

GOLD.append(v6_example(
    "v6_soft_every_role_01",
    "Data Analyst",
    v6_user(
        "Deloitte",
        "Data Analyst",
        "SQL, Excel, communication, teamwork.",
        "Meera interned at RetailCo writing SQL. Skills: SQL, Excel, communication, teamwork.",
    ),
    """MEERA SINGH
meera@email.com

PROFESSIONAL SUMMARY
Data analyst intern experienced in SQL reporting and Excel dashboards.

TECHNICAL SKILLS
Languages: SQL
Tools: Excel

SOFT SKILLS
""" + SOFT_SKILLS_LINE + """

PROFESSIONAL EXPERIENCE
Data Analyst Intern | RetailCo
• Wrote SQL reports for weekly operations reviews

EDUCATION
B.Sc. Statistics
""",
    category="soft_skills_split",
))

print("gold examples after 03d:", len(GOLD))
print("soft-skill gold ready (no auto-injection into existing examples)")
'''

nb['cells'][8]['source'] = [new_03d]
print("Patched V6-03d")

# Now update V6-03  to match
v6_03_src = ''.join(nb['cells'][5]['source'])
old_sys_line = 'Always include a separate SOFT SKILLS section with: Communication, Collaboration, Problem Solving, Critical Thinking, Adaptability, Time Management, Attention to Detail, Leadership, Initiative, Ownership.'
new_sys_line = 'Include a separate SOFT SKILLS section ONLY if the original resume has one. The soft skills list is: Communication, Collaboration, Problem Solving, Critical Thinking, Adaptability, Time Management, Attention to Detail, Leadership, Initiative, Ownership. Never mix soft skills into the TECHNICAL SKILLS groups.'

if old_sys_line in v6_03_src:
    v6_03_src = v6_03_src.replace(old_sys_line, new_sys_line)
    print("Patched V6-03 : SOFT SKILLS rule updated")
else:
    print("WARNING: Could not find the exact SOFT SKILLS line in V6-03")

# Also add link preservation rules to V6-03
old_contact = 'Section order: CONTACT, PROFESSIONAL SUMMARY, TECHNICAL SKILLS, PROFESSIONAL EXPERIENCE, PROJECTS, EDUCATION, CERTIFICATIONS.'
new_contact = old_contact + '\n- Preserve ALL contact links (LinkedIn, GitHub, portfolio, personal website) from the original resume.\n- If the original resume has links, format them as "Platform : url" lines in the contact block.'

if old_contact in v6_03_src:
    v6_03_src = v6_03_src.replace(old_contact, new_contact)
    print("Patched V6-03 : added link preservation rule")

# Add an explicit rewriting signal
old_return = 'Return ONLY a complete professional one-page resume.'
new_return = old_return + '\n- CRITICAL: You must rewrite the entire resume. Never copy the original text verbatim. Every bullet must be rephrased with stronger action verbs.'

if old_return in v6_03_src:
    v6_03_src = v6_03_src.replace(old_return, new_return)
    print("Patched V6-03 : added explicit rewriting signal")

nb['cells'][5]['source'] = [v6_03_src]

# Add a new gold example for link preservation (V6-03o style)
link_example = '''
# ============================================================
# V6-03o — LINK PRESERVATION EXAMPLES
# Teaches the model to extract and preserve LinkedIn, GitHub, portfolio links.
# Run after V6-03n.
# ============================================================

LINK_GOLD_JD = "Python, SQL, Docker, Kubernetes, REST APIs, React.js, CI/CD, Git, machine learning, Agile, problem-solving."

GOLD.append(v6_example(
    "v6_links_01",
    "Software Engineer",
    v6_user(
        "Amazon",
        "Software Engineer",
        LINK_GOLD_JD,
        """Sakhita Sree Gadde
(979) 344-8061 | sakhitasreerg2000@gmail.com | Bryan, TX
linkedin.com/in/sakhita-sree-gadde-87232119a
github.com/sakhita-sree-gadde
sakhitagadde.github.io

PROFESSIONAL SUMMARY
Data Science professional with Kubernetes orchestration and ML experience.

TECHNICAL SKILLS
Languages: Python, SQL, C++, Java, JavaScript
Core CS: Data Structures and Algorithms, Object-Oriented Programming
Frontend: React.js, HTML, CSS
Backend: REST APIs, FastAPI, Flask, Spring Boot, Node.js
Databases: DynamoDB, MySQL
AI / ML and GenAI: Pandas, Scikit-learn, Gemini API, LangChain, PyTorch, TensorFlow, Keras, Hugging Face, OpenCV
Tools and Cloud: Git, Docker, Kubernetes

PROFESSIONAL EXPERIENCE
Software Engineer | Infosys LTD | Jul 2022 - Dec 2023
- Built and deployed ML-powered applications using Python, TensorFlow, and Keras
- Automated CI/CD pipelines with Docker and Kubernetes
- Developed ETL pipelines with SQL and Pandas

PROJECTS
AI Resume Optimizer
- Built a full-stack app with React and FastAPI

EDUCATION
M.S. Data Science, Texas A and M University, Dec 2023
B.Tech, Amrita Vishwa Vidyapeetham, Jun 2021
""",
    """SAKHITA SREE GADDE
(979) 344-8061 | sakhitasreerg2000@gmail.com | Bryan, TX

LinkedIn : linkedin.com/in/sakhita-sree-gadde-87232119a
GitHub   : github.com/sakhita-sree-gadde
Portfolio: sakhitagadde.github.io

PROFESSIONAL SUMMARY
Data Science professional with Kubernetes orchestration experience and proficiency in machine learning, Generative AI, and ETL/ELT pipeline development.

TECHNICAL SKILLS
Languages: Python, SQL, C++, Java, JavaScript
Core CS: Data Structures and Algorithms, Object-Oriented Programming
Frontend: React.js, HTML, CSS
Backend: REST APIs, FastAPI, Flask, Spring Boot, Node.js
Databases: DynamoDB, MySQL
AI / ML and GenAI: Pandas, Scikit-learn, Gemini API, LangChain, PyTorch, TensorFlow, Keras, Hugging Face, OpenCV
Tools and Cloud: Git, Docker, Kubernetes

PROFESSIONAL EXPERIENCE
Software Engineer | Infosys LTD | Jul 2022 - Dec 2023
• Designed and deployed ML-powered applications using Python, TensorFlow, and Keras for production inference
• Automated CI/CD pipelines with Docker and Kubernetes, reducing deployment time by 30 percent
• Engineered ETL/ELT pipelines processing large-scale datasets with SQL and Pandas
• Integrated LLM-based services using Hugging Face and LangChain
• Led Agile sprint delivery of machine learning solutions with cross-functional teams

PROJECTS
AI Resume Optimizer
• Built a full-stack web application with React.js frontend and FastAPI backend for LLM-based resume optimization
• Deployed with Docker containers and Kubernetes orchestration

EDUCATION
Master of Science in Data Science (Computer Science), Texas A and M University, College Station, Texas, Dec 2023
Bachelor of Technology in Electronics and Communication Engineering, Amrita Vishwa Vidyapeetham, Kollam, India, Jun 2021
""",
    category="link_preservation",
))

print("Link preservation gold example added")
'''

# Find a good place to insert this - after V6-03n (cell 18)
# We'll add it as a new cell before V6-04 (cell 19)
# First, insert after cell 18
nb['cells'].insert(19, {"cell_type": "code", "metadata": {}, "outputs": [], "source": [link_example]})
print("Inserted V6-03o link preservation cell at index 19")

# Now update V6-08 training hyperparameters
v6_08_src = ''.join(nb['cells'][24]['source'])
old_epochs = 'num_train_epochs=1 if QUICK_SMOKE_TRAIN_V6 else 3,'
new_epochs = 'num_train_epochs=1 if QUICK_SMOKE_TRAIN_V6 else 4,'
if old_epochs in v6_08_src:
    v6_08_src = v6_08_src.replace(old_epochs, new_epochs)
    print("Patched V6-08: epochs 3 -> 4")

old_lr = 'learning_rate=5e-5,'
new_lr = 'learning_rate=3e-5,'
if old_lr in v6_08_src:
    v6_08_src = v6_08_src.replace(old_lr, new_lr)
    print("Patched V6-08: lr 5e-5 -> 3e-5")

nb['cells'][24]['source'] = [v6_08_src]

# Update V6-27 inference temperature
v6_27_src = ''.join(nb['cells'][27]['source'])
old_temp = 'temp=0.5, top_p=0.95, max_new=900'
new_temp = 'temp=0.7, top_p=0.92, max_new=1200'
if old_temp in v6_27_src:
    v6_27_src = v6_27_src.replace(old_temp, new_temp)
    print("Patched V6-27: temp 0.5->0.7, top_p 0.95->0.92, max_new 900->1200")

nb['cells'][27]['source'] = [v6_27_src]

# Also add CONTACT section handling in the FORCE_OPTIMIZE_SYSTEM prompt
old_force = 'You are an AI Resume Optimizer.\nYou MUST rewrite the entire resume. Never copy it unchanged.\nKeep only facts from the original. Rewrite bullets to be stronger.\nAdd JD keywords to Skills and Experience.\nSections: CONTACT, PROFESSIONAL SUMMARY, TECHNICAL SKILLS, SOFT SKILLS,\nPROFESSIONAL EXPERIENCE, PROJECTS, EDUCATION.\nWrite a 3-4 sentence summary. Group skills. Do not invent anything.'
new_force = old_force + '\n- ALWAYS preserve LinkedIn, GitHub, portfolio, and personal website links from the original resume.\n- Put links in the contact block as: Platform : url'
if old_force in v6_27_src:
    v6_27_src = v6_27_src.replace(old_force, new_force)
    print("Patched V6-27: added link preservation to inference prompt")

nb['cells'][27]['source'] = [v6_27_src]

# Save
with open(src, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("\nTotal cells:", len(nb['cells']))
print("Training notebook patched successfully!")
