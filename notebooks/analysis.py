import json
import re

with open('AI_Resume_Optimizer (1).ipynb', 'r') as f:
 nb = json.load(f)

cells = nb['cells']
total = len(cells)
print('=== OVERVIEW ===')
print('Total cells:', total)
print('Code cells:', sum(1 for c in cells if c['cell_type'] == 'code'))
print('Markdown cells:', sum(1 for c in cells if c['cell_type'] == 'markdown'))
print()

print('=== MARKDOWN HEADINGS ===')
mdh = 0
for i, c in enumerate(cells):
 if c['cell_type'] == 'markdown':
 s = ''.join(c['source'])
 for ln in s.split('\n'):
 st = ln.strip()
 if st.startswith('#'):
 print(' Cell ' + str(i) + ': ' + st)
 mdh += 1
 break
print('Total markdown headings:', mdh)
print()

print('=== FIRST LINE OF EVERY CODE CELL ===')
for i, c in enumerate(cells):
 if c['cell_type'] == 'code':
 fst = c['source'][0].strip() if c['source'] else '(empty)'
 print('C' + str(i) + '\t' + fst[:140])
print()

print('=== CELLS BY TOPIC ===')
topics = [
 ('MODEL LOADING', ['AutoModel', 'from_pretrained', 'BitsAndBytes', 'base_model']),
 ('LORA/ADAPTER', ['PeftModel', 'adapter_config', 'LoRA', 'adapters', 'merge_and_unload', 'get_peft_model', 'ResumeOptimizer-LoRA']),
 ('TRAINING', ['Trainer(', 'SFTTrainer', 'TrainingArguments', 'LoraConfig', 'lora_alpha', 'peft_config']),
 ('INFERENCE/GENERATION', ['model.generate', '.generate(', 'inference_model', 'GenerationConfig', 'max_new_tokens', 'QwenResumeModel', 'get_model']),
 ('PROMPT TEMPLATES', ['SYSTEM_RULES', 'system_prompt', 'optimization_prompt', 'build.*prompt', 'prompt_template']),
 ('SAFETY CHECKS', ['safety_gate', 'safety_check', 'hallucination', 'truthful', 'anti_halluc', 'keyword_stuffing', 'role_mismatch', 'unsupported.*skill', 'fake_']),
 ('PDF GENERATION', ['reportlab', 'HTML(', 'FPDF', 'pdfkit', 'WeasyPrint', 'Canvas', 'pdf_doc', 'generate.*pdf', '.pdf', 'ATS']),
 ('RESUME PARSING', ['resume.*pars', 'parse.*resume', 'extract.*section', 'parse_resume', 'ResumeParser', 'resume_text']),
 ('JD PARSING', ['JD.*analysis', 'analyze.*JD', 'job_description.*pars', 'JD.*keyword', 'JD.*structur', 'JD.*extract']),
]

for topic, pats in topics:
 print()
 print('--- ' + topic + ' ---')
 matched = 0
 for i, c in enumerate(cells):
 if c['cell_type'] != 'code':
 continue
 src = ''.join(c['source'])
 found = False
 for p in pats:
 if re.search(p, src, re.IGNORECASE):
 found = True
 break
 if found:
 matched += 1
 fst = c['source'][0].strip()[:140] if c['source'] else '(empty)'
 print(' Cell ' + str(i) + ': ' + fst)
 print(' (' + str(matched) + ' cells matched)')
