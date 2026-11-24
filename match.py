"""Match invoice lines to the store catalog and propose stock updates (never applied automatically)."""
from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher

from schema import Invoice

FUZZY_OK = 0.75      # at or above: suggest the match, but a person confirms it
FUZZY_MAYBE = 0.55   # below: treat as a new product


def load_catalog(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{"sku": r["sku"].strip(), "product": r["product"].strip(), "on_hand": int(r["on_hand"])}
                for r in csv.DictReader(f)]


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def name_score(a: str, b: str) -> float:
    """Blend of character similarity and how many of the catalog name's words appear in the line."""
    ta, tb = _tokens(a), _tokens(b)
    coverage = len(ta & tb) / max(len(tb), 1)
    return round(0.5 * SequenceMatcher(None, a.lower(), b.lower()).ratio() + 0.5 * coverage, 2)


def receiving_plan(inv: Invoice, catalog: list[dict]) -> list[dict]:
    by_sku = {c["sku"].upper(): c for c in catalog}
    plan = []
    for ln in inv.lines:
        row = {"line": ln.description, "invoice_sku": ln.sku, "qty": ln.quantity, "sku": None, "product": None,
               "on_hand": None, "new_on_hand": None, "match": "none", "confidence": 0.0, "needs_review": True, "note": ""}
        hit = by_sku.get((ln.sku or "").strip().upper())
        if hit:
            row.update(sku=hit["sku"], product=hit["product"], match="exact SKU", confidence=1.0, needs_review=False)
        elif ln.sku:
            # A SKU we don't stock is a new product. Never fuzzy-match it onto something else.
            best = max(catalog, key=lambda c: name_score(ln.description, c["product"]))
            row["note"] = (f"SKU {ln.sku} isn't in the catalog: add it as a new product? "
                           f"(closest name: {best['product']}, {name_score(ln.description, best['product'])}, not used)")
        else:
            best = max(catalog, key=lambda c: name_score(ln.description, c["product"]))
            s = name_score(ln.description, best["product"])
            if s >= FUZZY_MAYBE:
                row.update(sku=best["sku"], product=best["product"], match="name (fuzzy)", confidence=s,
                           note="No SKU on the invoice: matched by name. Confirm before receiving.")
            else:
                row["note"] = "No SKU and no close name match: new product?"
        if row["sku"]:
            on = next(c["on_hand"] for c in catalog if c["sku"] == row["sku"])
            row.update(on_hand=on, new_on_hand=on + ln.quantity)
        plan.append(row)
    return plan
