"""Invoice Ingestor: invoice file -> structured invoice -> math checks -> catalog match -> proposed stock update.

Two ways to read the document:
  mode="text"   : pull the PDF's text layer and give the model text (fails on scans and photos)
  mode="vision" : render the pages as images and let a vision-language model read them
"""
from __future__ import annotations

import os
from typing import Any, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

import docs
from checks import check_invoice
from match import load_catalog, receiving_plan
from schema import Invoice

load_dotenv()

PROMPT = """Extract this supplier invoice.
Rules:
- Copy every number exactly as printed. Do NOT fix math, even if it looks wrong.
- One entry per line item, in order. Keep the SKU/item code exactly as printed; leave it empty if a line has none.
- Shipping/freight goes in `shipping`. Tax goes in `tax`. Use 0 if not printed.
- Never invent values."""


def get_llm(provider: str = "anthropic"):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), temperature=0, max_tokens=3000,
                             max_retries=3, timeout=120)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b"), temperature=0)
    raise ValueError(provider)


class State(TypedDict, total=False):
    path: str
    mode: str
    catalog_path: str
    llm: Any
    invoice: Invoice
    issues: list
    plan: list
    error: Optional[str]


def extract(state: State) -> State:
    if state.get("invoice"):
        return {}
    if state["mode"] == "text":
        try:
            text = docs.pdf_text(state["path"])
        except docs.NoTextLayer as e:
            return {"error": str(e)}
        model = state["llm"].with_structured_output(Invoice)
        inv = model.invoke([("system", PROMPT), ("human", f"Invoice text:\n\n{text}")])
    else:
        model = state["llm"].with_structured_output(Invoice)
        content = [{"type": "image_url", "image_url": {"url": docs.to_data_url(img)}} for img in docs.page_images(state["path"])]
        content.append({"type": "text", "text": "Extract this invoice."})
        inv = model.invoke([("system", PROMPT), ("human", content)])
    return {"invoice": inv}


def check(state: State) -> State:
    return {"issues": check_invoice(state["invoice"])}


def match(state: State) -> State:
    return {"plan": receiving_plan(state["invoice"], load_catalog(state["catalog_path"]))}


def build_graph():
    g = StateGraph(State)
    g.add_node("extract", extract)
    g.add_node("check", check)
    g.add_node("match", match)
    g.set_entry_point("extract")
    g.add_conditional_edges("extract", lambda s: END if s.get("error") else "check", {"check": "check", END: END})
    g.add_edge("check", "match")
    g.add_edge("match", END)
    return g.compile()


def run(path: str, catalog_path: str, mode: str = "vision", llm=None, invoice: Invoice | None = None) -> State:
    state: State = {"path": path, "mode": mode, "catalog_path": catalog_path, "llm": llm or (None if invoice else get_llm())}
    if invoice is not None:
        state["invoice"] = invoice
    return build_graph().invoke(state)
