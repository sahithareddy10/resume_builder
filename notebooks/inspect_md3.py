import json, sys
nb = json.load(open('/sessions/practical-amazing-ride/mnt/ai_resume_jh/notebooks/AI_Resume_Optimizer (1).ipynb'))
cells = nb['cells']
print('Total cells:', len(cells))
for i, c in enumerate(cells):
	if c['cell_type'] == 'markdown':
		src = ''.join(c['source']).strip()
		if src.startswith('#'):
			print('Cell', i, ':', src[:200])
