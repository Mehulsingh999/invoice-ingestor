"""Text layer vs. vision: run every sample invoice both ways and score the extraction.

  python compare.py
"""
from __future__ import annotations

import json
import pathlib
import time

import agent
from schema import Invoice

SAMPLES = pathlib.Path(__file__).parent / "sample_data"
CATALOG = str(SAMPLES / "catalog.csv")


def fields(inv: Invoice) -> list:
    out = [inv.invoice_number, inv.total, inv.subtotal, inv.shipping, inv.tax, len(inv.lines)]
    for ln in inv.lines:
        out += [(ln.sku or None), ln.quantity, ln.unit_price, ln.line_total]
    return out


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.005
    return (str(a).strip().upper() if a is not None else None) == (str(b).strip().upper() if b is not None else None)


def main():
    llm = agent.get_llm()
    files = sorted(p for p in SAMPLES.iterdir() if p.suffix in (".pdf", ".png"))
    results = {}
    for mode in ("text", "vision"):
        ok = total = read = 0
        secs = 0.0
        rows = []
        for f in files:
            truth = Invoice.model_validate(json.loads(f.with_suffix(".json").read_text()))
            want = fields(truth)
            t0 = time.time()
            out = agent.run(str(f), CATALOG, mode=mode, llm=llm)
            secs += time.time() - t0
            if out.get("error"):
                got_ok, note = 0, "could not read: " + out["error"]
            else:
                read += 1
                got = fields(out["invoice"])
                got_ok = sum(same(a, b) for a, b in zip(got, want))
                issues = [i["code"] for i in out["issues"]]
                note = f"issues={issues or 'none'}"
            ok, total = ok + got_ok, total + len(want)
            rows.append((f.name, f"{got_ok}/{len(want)}", note))
        results[mode] = {"read": read, "n": len(files), "acc": ok / total, "secs": secs / len(files), "rows": rows}
    for mode, r in results.items():
        print(f"\n== {mode} ==")
        for name, score, note in r["rows"]:
            print(f"  {name:28} {score:>6}  {note}")
    print("\n| Approach | Invoices it could read | Fields extracted exactly | Avg seconds |")
    print("| --- | --- | --- | --- |")
    for mode, r in results.items():
        label = "PDF text layer + LLM" if mode == "text" else "Vision model on page images"
        print(f"| {label} | {r['read']}/{r['n']} | {r['acc']:.0%} | {r['secs']:.1f} |")


if __name__ == "__main__":
    main()
