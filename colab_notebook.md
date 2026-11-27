# ============================================================
# CELL 1 — Install Dependencies
# ============================================================
# Run this cell first, then restart the runtime (Runtime → Restart runtime)
# and run it again to confirm imports work.

print("Installing dependencies...")
!pip install -q pdfplumber python-docx reportlab pydantic spacy nltk

import nltk
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt_tab', quiet=True)

print("Done! Now restart the runtime and re-run this cell to verify imports.")
