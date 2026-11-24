"""Exact math checks on an extracted invoice (no AI)."""
from __future__ import annotations

from collections import Counter

from schema import Invoice

CENT = 0.01


def r(x: float) -> float:
    return round(x + 0.0, 2)


def check_invoice(inv: Invoice) -> list[dict]:
    issues = []
    for i, ln in enumerate(inv.lines, 1):
        if ln.unit_price is not None:
            exp = r(ln.quantity * ln.unit_price)
            if abs(ln.line_total - exp) > CENT:
                issues.append({"code": "LINE_MATH", "severity": "high", "amount": r(ln.line_total - exp),
                               "message": f"Line {i} '{ln.description}': {ln.quantity:g} x ${ln.unit_price:.2f} = "
                                          f"${exp:.2f}, but the invoice charges ${ln.line_total:.2f}."})
    dupes = Counter((ln.sku or ln.description.lower(), ln.line_total) for ln in inv.lines)
    for (key, amt), n in dupes.items():
        if n > 1:
            issues.append({"code": "DUPLICATE_LINE", "severity": "medium", "amount": r(amt * (n - 1)),
                           "message": f"'{key}' for ${amt:.2f} appears {n} times."})
    lines_sum = r(sum(ln.line_total for ln in inv.lines))
    if inv.subtotal is not None and abs(inv.subtotal - lines_sum) > CENT:
        issues.append({"code": "SUBTOTAL_MISMATCH", "severity": "high", "amount": r(inv.subtotal - lines_sum),
                       "message": f"Lines add up to ${lines_sum:.2f}, but the subtotal says ${inv.subtotal:.2f}."})
    base = inv.subtotal if inv.subtotal is not None else lines_sum
    exp_total = r(base + inv.shipping + inv.tax)
    if abs(inv.total - exp_total) > CENT:
        issues.append({"code": "TOTAL_MISMATCH", "severity": "high", "amount": r(inv.total - exp_total),
                       "message": f"Subtotal + shipping + tax = ${exp_total:.2f}, but the total due is ${inv.total:.2f}."})
    return issues
