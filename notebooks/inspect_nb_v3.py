import json

with open('AI_Resume_Optimizer (1).ipynb') as f:
	nb = json.load(f)
cells = nb['cells']
print('Total cells:', len(cells))
print()
print('=== MARKDOWN HEADINGS ===')
for i, c in enumerate(cells):
	if c['cell_type'] == 'markdown':
		src = ''.join(c['source']).strip()
		if src.startswith('#'):
			print(f'Cell {i}: {src[:200]}')
