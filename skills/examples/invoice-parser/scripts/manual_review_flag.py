"""manual_review_flag — flag an invoice for manual review."""
from __future__ import annotations

import json
import sys
import uuid
from typing import Any


def skill_entry(file_path: str = "", reason: str = "Validation failed") -> dict[str, Any]:
    """Create a manual-review ticket for *file_path*."""
    ticket_id = f"MR-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "message": f"Flagged for manual review: {ticket_id} — {reason}",
        "data": {"ticket_id": ticket_id, "file_path": file_path, "reason": reason},
        "next_actions": [],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
