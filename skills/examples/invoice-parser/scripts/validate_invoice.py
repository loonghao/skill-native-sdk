"""validate_invoice — validate parsed invoice data for completeness."""
from __future__ import annotations

import json
import sys
from typing import Any


def skill_entry(invoice_data: dict | None = None, **kwargs: Any) -> dict[str, Any]:
    """Validate *invoice_data* dict returned by parse_invoice."""
    data = invoice_data or kwargs.get("data") or {}

    errors = []
    if not data.get("vendor"):
        errors.append("Missing vendor name")
    if not data.get("invoice_number"):
        errors.append("Missing invoice number")
    total = data.get("total", 0)
    if not isinstance(total, (int, float)) or total <= 0:
        errors.append(f"Invalid total: {total!r}")
    if not data.get("line_items"):
        errors.append("No line items found")

    valid = len(errors) == 0
    return {
        "success": valid,
        "message": "Invoice valid" if valid else f"Validation failed: {'; '.join(errors)}",
        "data": {"valid": valid, "errors": errors},
        "next_actions": ["post_to_accounting"] if valid else ["manual_review_flag"],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    # When the function accepts **kwargs, pass everything through so the
    # chain-injected "data" key reaches kwargs.get("data") untouched.
    filtered = params if has_var_keyword else {
        k: v for k, v in params.items() if k in sig.parameters
    }
    result = skill_entry(**filtered)
    print(json.dumps(result))
