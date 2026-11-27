import json

with open('AI_Resume_Optimizer (1).ipynb') as f:
 nb = json.load(f)

cells = nb['cells']
print('Total cells:', len(cells))
code_cells = sum(1 for c in cells if c['cell_type'] == 'code')
md_cells = sum(1 for c in cells if c['cell_type'] == 'markdown')
print(f'{code_cells} code, {md_cells} markdown')
print()
print('=== FIRST 15 MARKDOWN CELLS ===')
count = 0
for i, c in enumerate(cells):
 if c['cell_type'] == 'markdown':
 src = ''.join(c['source']).strip()
 if src:
 print(f'[{i}] {src[:150]}')
 count += 1
 if count >= 15:
 break

print()
print('=== KEY CODE CELLS ===')
keywords = ['model', 'train', 'lora', 'qlora', 'inference', 'generate', 'optimize', 'safety', 'pdf', 'parse', 'adapter', 'prompt']
for i, c in enumerate(cells):
 if c['cell_type'] == 'code':
 src = ''.join(c['source']).strip().lower()
 if any(kw in src for kw in keywords):
 first_line = ''.join(c['source']).strip().split('\n')[0][:120]
 print(f'[Cell {i}] {first_line}')
