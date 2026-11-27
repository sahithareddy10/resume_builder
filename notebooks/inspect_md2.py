import json

nb_path = '/sessions/practical-amazing-ride/mnt/ai_resume_jh/notebooks/AI_Resume_Optimizer (1).ipynb'
with open(nb_path) as f:
	nb = json.load(f)

cells = nb['cells']
print('Total cells:', len(cells))
code_cells = sum(1 for c in cells if c['cell_type'] == 'code')
md_cells = sum(1 for c in cells if c['cell_type'] == 'markdown')
print(f'{code_cells} code, {md_cells} markdown')
print()

print('=== MARKDOWN HEADINGS ===')
for i, c in enumerate(cells):
	if c['cell_type'] != 'markdown':
		continue
	src = ''.join(c['source']).strip()
	if src.startswith('#'):
		print(f'Cell {i}: {src[:200]}')
