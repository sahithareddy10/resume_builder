import py_compile

files = [
 "app/core/config.py",
 "app/models/schemas.py",
 "app/services/pdf_generator.py",
 "app/services/ats_scorer.py",
 "app/services/resume_parser.py",
 "app/services/ai_engine.py",
 "app/services/optimizer.py",
 "app/api/v1/__init__.py",
 "app/api/v1/routes.py",
 "app/main.py",
]
for f in files:
 try:
 py_compile.compile(f, doraise=True)
 print(f"OK: {f}")
 except py_compile.PyCompileError as e:
 print(f"ERROR: {f}: {e}")
