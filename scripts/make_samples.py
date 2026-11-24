"""Generates 4 sample supplier invoices (made up) plus the correct extraction for each, and a product catalog.

01 clean PDF · 02 PDF with a line-math error · 03 scanned image (tilted, noisy, no text layer)
04 phone-photo style image with a line that has no SKU and a product that isn't in the catalog
"""
import csv
import json
import pathlib
import random

import pypdfium2 as pdfium
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

OUT = pathlib.Path(__file__).resolve().parents[1] / "sample_data"
random.seed(7)

CATALOG = [
    ("BEV-COF-001", "Espresso Beans 1kg", 9), ("BEV-COF-002", "Medium Roast Beans 1kg", 4),
    ("BEV-COF-003", "Espresso Ground 200g", 2), ("BEV-TEA-002", "Green Tea 50ct", 15),
    ("BEV-SYR-001", "Vanilla Syrup 750ml", 3), ("SNK-CHP-001", "Sea Salt Chips 12pk", 6),
    ("DRY-MLK-004", "Oat Milk 1L", 11), ("BAK-BRD-002", "Sourdough Loaf", 0),
]

INVOICES = {
    "01_clean": dict(supplier="Lone Star Coffee Supply", invoice_number="INV-1001", date="2026-11-18", lines=[
        ("BEV-COF-001", "Espresso Beans 1kg", 6, 18.50, 111.00),
        ("BEV-COF-003", "Espresso Ground 200g", 24, 4.25, 102.00),
        ("BEV-TEA-002", "Green Tea 50ct", 12, 3.10, 37.20)], subtotal=250.20, shipping=0.0, tax=0.0, total=250.20),
    "02_math_error": dict(supplier="Metro Grocery Wholesale", invoice_number="MG-55812", date="2026-11-19", lines=[
        ("SNK-CHP-001", "Sea Salt Chips 12pk", 10, 9.80, 98.00),
        ("DRY-MLK-004", "Oat Milk 1L", 36, 2.15, 79.40),  # should be 77.40
        ("BAK-BRD-002", "Sourdough Loaf", 20, 2.60, 52.00)], subtotal=229.40, shipping=0.0, tax=0.0, total=229.40),
    "03_scanned": dict(supplier="Lone Star Coffee Supply", invoice_number="INV-1007", date="2026-11-20", lines=[
        ("BEV-COF-002", "Medium Roast Beans 1kg", 8, 16.75, 134.00),
        ("BEV-SYR-001", "Vanilla Syrup 750ml", 6, 7.40, 44.40)], subtotal=178.40, shipping=12.00, tax=0.0, total=190.40),
    "04_photo_unknown_item": dict(supplier="Metro Grocery Wholesale", invoice_number="MG-55840", date="2026-11-21", lines=[
        ("", "Oatly Barista Oat Milk 1L", 24, 2.15, 51.60),
        ("BEV-SYR-009", "Pumpkin Spice Syrup 750ml", 4, 7.90, 31.60)], subtotal=83.20, shipping=0.0, tax=0.0, total=83.20),
}


def make_pdf(path, inv):
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=0.7 * inch)
    s = getSampleStyleSheet()
    rows = [["SKU", "Description", "Qty", "Unit price", "Amount"]]
    rows += [[sku or "", d, str(q), f"${u:,.2f}", f"${t:,.2f}"] for sku, d, q, u, t in inv["lines"]]
    rows += [["", "", "", "Subtotal", f"${inv['subtotal']:,.2f}"]]
    if inv["shipping"]:
        rows += [["", "", "", "Shipping", f"${inv['shipping']:,.2f}"]]
    rows += [["", "", "", "Tax", f"${inv['tax']:,.2f}"], ["", "", "", "TOTAL DUE", f"${inv['total']:,.2f}"]]
    t = Table(rows, colWidths=[1.2 * inch, 2.9 * inch, 0.6 * inch, 1.1 * inch, 1.1 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, len(inv["lines"])), 0.5, colors.grey),
                           ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold")]))
    doc.build([Paragraph(f"<b>{inv['supplier']}</b>", s["Title"]),
               Paragraph(f"Invoice {inv['invoice_number']} &nbsp;&nbsp; Date: {inv['date']}", s["Normal"]),
               Paragraph("Bill to: Downtown Store", s["Normal"]), Spacer(1, 18), t])


def to_image(pdf_path, png_path, angle, noise, blur):
    page = pdfium.PdfDocument(str(pdf_path))[0]
    img = page.render(scale=150 / 72).to_pil().convert("L")
    img = img.rotate(angle, expand=True, fillcolor=245)
    px = img.load()
    w, h = img.size
    for _ in range(int(w * h * noise)):
        x, y = random.randrange(w), random.randrange(h)
        px[x, y] = random.randint(90, 200)
    img = img.filter(ImageFilter.GaussianBlur(blur))
    img.save(png_path)


for name, inv in INVOICES.items():
    pdf = OUT / f"{name}.pdf"
    make_pdf(pdf, inv)
    if name.startswith("03"):
        to_image(pdf, OUT / f"{name}.png", angle=1.6, noise=0.02, blur=0.8)
        pdf.unlink()  # a scan has no text layer: keep only the image
    elif name.startswith("04"):
        to_image(pdf, OUT / f"{name}.png", angle=-2.4, noise=0.01, blur=1.0)
        pdf.unlink()
    truth = {"supplier": inv["supplier"], "invoice_number": inv["invoice_number"], "date": inv["date"],
             "lines": [{"sku": sku or None, "description": d, "quantity": q, "unit_price": u, "line_total": t}
                       for sku, d, q, u, t in inv["lines"]],
             "subtotal": inv["subtotal"], "shipping": inv["shipping"], "tax": inv["tax"], "total": inv["total"]}
    (OUT / f"{name}.json").write_text(json.dumps(truth, indent=2))

with open(OUT / "catalog.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sku", "product", "on_hand"])
    w.writerows(CATALOG)
(OUT / "README.md").write_text("Made-up supplier invoices for testing. Each invoice has a .json with the correct extraction.\n"
                               "catalog.csv is a sample store catalog with current stock.\n")
print(sorted(p.name for p in OUT.iterdir()))
