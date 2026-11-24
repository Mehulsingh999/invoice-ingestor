"""Streamlit demo: streamlit run app.py"""
import pathlib
import tempfile

import pandas as pd
import streamlit as st

import agent
import docs

S = pathlib.Path(__file__).parent / "sample_data"
CATALOG = str(S / "catalog.csv")

st.set_page_config(page_title="Invoice Ingestor", page_icon="📦", layout="wide")
st.title("Invoice Ingestor")
st.caption("Supplier invoice in (PDF, scan or photo) → checked → matched to your catalog → stock update you approve.")

mode = st.sidebar.radio("How to read it", ["vision", "text"],
                        format_func=lambda m: "Vision model (sees the page)" if m == "vision" else "PDF text layer only")
src = st.radio("Invoice", ["Sample", "Upload"], horizontal=True)
if src == "Sample":
    name = st.selectbox("Sample invoice", sorted(p.name for p in S.iterdir() if p.suffix in (".pdf", ".png")))
    path = str(S / name)
else:
    up = st.file_uploader("PDF or photo", type=["pdf", "png", "jpg", "jpeg"])
    if not up:
        st.stop()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(up.name).suffix)
    tmp.write(up.getvalue())
    tmp.close()
    path = tmp.name

left, right = st.columns([2, 3])
left.image(docs.page_images(path)[0], caption="What the model sees", width='stretch')

key = f"{path}|{mode}"
if right.button("Ingest", type="primary"):
    with right:
        with st.spinner("Reading the invoice..."):
            try:
                st.session_state["result"] = (key, agent.run(path, CATALOG, mode=mode))
            except Exception as e:
                st.session_state["result"] = (key, {"error": f"{type(e).__name__}: {e}"})

# Keep the result across reruns (editing the table or clicking download reruns the script)
saved = st.session_state.get("result")
if not saved or saved[0] != key:
    right.info("Pick an invoice and click **Ingest**.")
    st.stop()
out = saved[1]

with right:
    if out.get("error"):
        st.error(out["error"])
        if "text layer" in out["error"]:
            st.info("Switch to the vision model in the sidebar: it reads scans and photos.")
        elif "api_key" in out["error"].lower() or "authentication" in out["error"].lower():
            st.info("Check ANTHROPIC_API_KEY in your .env file, then restart the app.")
        st.stop()
    inv = out["invoice"]
    st.subheader(f"{inv.supplier} · {inv.invoice_number} · {inv.date or ''}")
    st.metric("Total due", f"${inv.total:,.2f}")
    if out["issues"]:
        for i in out["issues"]:
            st.error(f"**{i['code']}**: {i['message']}")
    else:
        st.success("The math checks out.")
    st.subheader("Proposed stock update")
    plan = pd.DataFrame(out["plan"])
    plan.insert(0, "approve", ~plan["needs_review"])
    edited = st.data_editor(plan[["approve", "line", "invoice_sku", "qty", "sku", "product", "on_hand", "new_on_hand",
                                  "match", "confidence", "note"]], hide_index=True, disabled=["line", "qty", "note"],
                            key=f"plan|{key}")
    approved = edited[edited["approve"] & edited["sku"].notna()]
    st.download_button("Download approved updates (CSV)", approved[["sku", "product", "qty", "new_on_hand"]].to_csv(index=False),
                       file_name=f"receiving_{inv.invoice_number}.csv")
    with st.expander("Extracted invoice (structured output)"):
        st.json(inv.model_dump())
