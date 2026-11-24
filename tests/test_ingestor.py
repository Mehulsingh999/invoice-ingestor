import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
import docs  # noqa: E402
from checks import check_invoice  # noqa: E402
from match import load_catalog, receiving_plan  # noqa: E402
from schema import Invoice  # noqa: E402

S = ROOT / "sample_data"
CAT = load_catalog(str(S / "catalog.csv"))


def inv(name):
    return Invoice.model_validate(json.loads((S / f"{name}.json").read_text()))


def test_clean_invoices_have_no_issues():
    for n in ("01_clean", "03_scanned", "04_photo_unknown_item"):
        assert check_invoice(inv(n)) == [], n


def test_line_math_error_is_caught():
    issues = check_invoice(inv("02_math_error"))
    assert [i["code"] for i in issues] == ["LINE_MATH"]
    assert issues[0]["amount"] == 2.00


def test_exact_sku_matches_update_stock():
    plan = receiving_plan(inv("01_clean"), CAT)
    assert all(p["match"] == "exact SKU" and not p["needs_review"] for p in plan)
    espresso = next(p for p in plan if p["sku"] == "BEV-COF-003")
    assert (espresso["on_hand"], espresso["new_on_hand"]) == (2, 26)


def test_no_sku_line_is_fuzzy_matched_but_needs_review():
    oat = receiving_plan(inv("04_photo_unknown_item"), CAT)[0]
    assert oat["sku"] == "DRY-MLK-004" and oat["match"] == "name (fuzzy)" and oat["needs_review"]


def test_unknown_sku_is_never_fuzzy_matched():
    pumpkin = receiving_plan(inv("04_photo_unknown_item"), CAT)[1]
    assert pumpkin["sku"] is None and "new product" in pumpkin["note"]


def test_scans_have_no_text_layer_but_pdfs_do():
    assert "INV-1001" in docs.pdf_text(str(S / "01_clean.pdf"))
    for n in ("03_scanned.png", "04_photo_unknown_item.png"):
        try:
            docs.pdf_text(str(S / n))
            assert False, n
        except docs.NoTextLayer:
            pass


def test_text_mode_on_scan_stops_without_calling_a_model():
    out = agent.run(str(S / "03_scanned.png"), str(S / "catalog.csv"), mode="text", llm=object())
    assert "no text layer" in out["error"]


def test_graph_offline_with_given_invoice():
    out = agent.run(str(S / "02_math_error.pdf"), str(S / "catalog.csv"), invoice=inv("02_math_error"))
    assert out["issues"][0]["code"] == "LINE_MATH" and len(out["plan"]) == 3
