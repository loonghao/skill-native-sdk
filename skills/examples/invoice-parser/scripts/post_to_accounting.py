"""post_to_accounting — post validated invoice to accounting system (simulation)."""
from __future__ import annotations

import json
import sys
import uuid
from typing import Any


def skill_entry(
    vendor: str = "",
    total: float = 0.0,
    invoice_number: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Simulate posting invoice to accounting. Returns an entry ID."""
    if not vendor:
        return {
            "success": False,
            "error": "vendor is required",
            "message": "Cannot post: missing vendor",
            "next_actions": [],
        }

    entry_id = f"ACC-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "message": f"Posted {invoice_number or 'invoice'} from {vendor} (${total:,.2f}) → {entry_id}",
        "data": {"entry_id": entry_id, "vendor": vendor, "total": total},
        "next_actions": [],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    filtered = params if has_var_keyword else {
        k: v for k, v in params.items() if k in sig.parameters
    }
    result = skill_entry(**filtered)
    print(json.dumps(result))
