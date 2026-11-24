"""Structured shape of a supplier invoice (what the model must fill in)."""
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    sku: Optional[str] = Field(default=None, description="Supplier SKU/item code exactly as printed; empty if none")
    description: str = Field(description="Item description exactly as printed")
    quantity: float = Field(description="Quantity shipped")
    unit_price: Optional[float] = Field(default=None, description="Price per unit as printed")
    line_total: float = Field(description="Line amount as printed")


class Invoice(BaseModel):
    supplier: str
    invoice_number: str
    date: Optional[str] = Field(default=None, description="Invoice date as YYYY-MM-DD")
    lines: list[InvoiceLine] = Field(description="Every line item, in printed order")
    subtotal: Optional[float] = None
    shipping: float = 0
    tax: float = 0
    total: float = Field(description="Total due as printed")
