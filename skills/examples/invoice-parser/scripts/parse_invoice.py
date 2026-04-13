"""parse_invoice — extract structured data from an invoice file.

This is a simulation implementation. A real implementation would use
an OCR library (Tesseract, AWS Textract, etc.).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def skill_entry(file_path: str, currency: str = "USD") -> dict[str, Any]:
    """Parse *file_path* and return structured invoice data."""
    p = Path(file_path)
    if not p.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "message": "Invoice file does not exist",
        }

    # Simulation: return mock data based on filename
    return {
        "success": True,
        "message": f"Parsed invoice from {p.name}",
        "data": {
            "vendor": "ACME Corp",
            "invoice_number": "INV-2026-001",
            "currency": currency,
            "total": 1250.00,
            "tax": 125.00,
            "line_items": [
                {"description": "Consulting services", "quantity": 10, "unit_price": 100.00, "total": 1000.00},
                {"description": "Travel expenses", "quantity": 1, "unit_price": 125.00, "total": 125.00},
                {"description": "Materials", "quantity": 5, "unit_price": 25.00, "total": 125.00},
            ],
        },
        "next_actions": ["validate_invoice", "post_to_accounting"],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
