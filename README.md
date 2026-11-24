# Invoice Ingestor

Build #4 of my 30-day AI series. Concept: **document parsing with vision-language models**.

Stores get supplier invoices as PDFs, scans and phone photos, and someone types each line into inventory.
This reads the invoice, checks the math, matches every line to the store catalog and proposes a stock
update that a person approves. Nothing changes stock automatically.

```
invoice (PDF / scan / photo)
  -> extract   vision model reads the page images  (or: PDF text layer + LLM, for comparison)
  -> check     plain Python: line math, duplicates, subtotal, total
  -> match     exact SKU first; fuzzy name match only for lines with no SKU, always flagged for review
  -> plan      proposed new stock levels -> you approve -> CSV for StoreIO
```

Matching rule learned the hard way: a line with a SKU that isn't in the catalog is a **new product**,
never fuzzy-matched. By name alone, "Pumpkin Spice Syrup 750ml" scores 0.63 against "Vanilla Syrup 750ml".

## Run it (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env      # add your ANTHROPIC_API_KEY
pytest -q                   # 8 tests, offline
streamlit run app.py
python compare.py           # text layer vs. vision on the 4 sample invoices
```

`sample_data/` holds 4 made-up invoices (clean PDF, PDF with a math error, tilted noisy scan, phone-style
photo), each with a `.json` of the correct extraction, plus `catalog.csv`. Regenerate with `scripts/make_samples.py`.
