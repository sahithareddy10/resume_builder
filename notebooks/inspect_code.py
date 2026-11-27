import json
nb = json.load(open('/sessions/practical-amazing-ride/mnt/ai_resume_jh/notebooks/AI_Resume_Optimizer (1).ipynb'))
cells = nb['cells']
print('Total cells:', len(cells))
for i, c in enumerate(cells):
	if c['cell_type'] != 'code':
		continue
	src = ''.join(c['source']).strip()
	if not src:
		continue
	first = src.split('\n')[0][:120]
	print(f'Cell {i}: {first}')
