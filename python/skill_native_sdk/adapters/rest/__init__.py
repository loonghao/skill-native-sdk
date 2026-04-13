"""REST adapter for skill-native-sdk.

Exposes a :class:`SkillRegistry` as a RESTful HTTP API.

Two backends are supported (auto-selected):
1. **FastAPI** (recommended) — if ``fastapi`` and ``uvicorn`` are installed.
2. **stdlib** ``http.server`` — zero-dependency fallback, always available.

Usage::

    from skill_native_sdk import SkillRegistry
    from skill_native_sdk.adapters.rest import RESTServer

    server = RESTServer(SkillRegistry.from_path("./skills"))
    server.serve(host="0.0.0.0", port=8000)

API endpoints (both backends):

    GET  /skills                       — list all skills (lightweight metadata)
    GET  /skills/{skill_name}          — describe a skill (tools, runtime, permissions)
    POST /skills/{skill_name}/{tool}   — execute a tool
                                         Body: {"params": {...}}
                                         Response: ToolResult JSON

Optional FastAPI install::

    pip install skill-native-sdk[rest]
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ...executor import SkillExecutor
from ...registry import SkillRegistry


class RESTServer:
    """HTTP server that exposes a :class:`SkillRegistry` as a REST API."""

    def __init__(self, registry: SkillRegistry, name: str = "skill-native-sdk") -> None:
        self.registry = registry
        self.executor = SkillExecutor(registry)
        self.name = name

    # ── Route handlers (backend-independent) ──────────────────────────────────

    def _list_skills(self) -> Dict[str, Any]:
        skills = []
        for spec in self.registry:
            skills.append({
                "name": spec.name,
                "domain": spec.domain,
                "version": spec.version,
                "description": spec.description,
                "tags": spec.tags,
                "tool_count": len(spec.tools),
            })
        return {"skills": skills, "count": len(skills)}

    def _describe_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        spec = self.registry.get(skill_name)
        if spec is None:
            return None
        return {
            "name": spec.name,
            "domain": spec.domain,
            "version": spec.version,
            "description": spec.description,
            "tags": spec.tags,
            "runtime": {"type": spec.runtime.type, "entry": spec.runtime.entry},
            "permissions": {"network": spec.permissions.network, "filesystem": spec.permissions.filesystem},
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "read_only": t.read_only,
                    "destructive": t.destructive,
                    "idempotent": t.idempotent,
                    "input": {k: {"type": v.type, "required": v.required, "description": v.description}
                              for k, v in t.input.items()},
                }
                for t in spec.tools
            ],
        }

    def _execute_tool(self, skill_name: str, tool_name: str, body: Dict[str, Any]) -> Dict[str, Any]:
        params = body.get("params", {})
        result = self.executor.execute(skill_name, tool_name, params)
        return result.to_dict()

    # ── FastAPI backend ────────────────────────────────────────────────────────

    def _serve_fastapi(self, host: str, port: int) -> None:
        try:
            import uvicorn
            from fastapi import FastAPI, HTTPException
            from fastapi.responses import JSONResponse
            from pydantic import BaseModel
        except ImportError as exc:
            raise ImportError(
                "FastAPI backend requires: pip install skill-native-sdk[rest]"
            ) from exc

        app = FastAPI(title=self.name, description="skill-native-sdk REST API")

        class ExecuteBody(BaseModel):
            params: Dict[str, Any] = {}

        @app.get("/skills")
        async def list_skills():
            return JSONResponse(self._list_skills())

        @app.get("/skills/{skill_name}")
        async def describe_skill(skill_name: str):
            data = self._describe_skill(skill_name)
            if data is None:
                raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
            return JSONResponse(data)

        @app.post("/skills/{skill_name}/{tool_name}")
        async def execute_tool(skill_name: str, tool_name: str, body: ExecuteBody):
            return JSONResponse(self._execute_tool(skill_name, tool_name, {"params": body.params}))

        uvicorn.run(app, host=host, port=port)

    # ── stdlib http.server backend ────────────────────────────────────────────

    def _serve_stdlib(self, host: str, port: int) -> None:
        import http.server

        server_self = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # suppress default logs
                pass

            def _send_json(self, code: int, data: Any) -> None:
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                parts = [p for p in self.path.split("/") if p]
                if parts == ["skills"]:
                    self._send_json(200, server_self._list_skills())
                elif len(parts) == 2 and parts[0] == "skills":
                    data = server_self._describe_skill(parts[1])
                    if data is None:
                        self._send_json(404, {"error": f"Skill '{parts[1]}' not found"})
                    else:
                        self._send_json(200, data)
                else:
                    self._send_json(404, {"error": "Not found"})

            def do_POST(self) -> None:
                parts = [p for p in self.path.split("/") if p]
                if len(parts) == 3 and parts[0] == "skills":
                    length = int(self.headers.get("Content-Length", 0))
                    raw = self.rfile.read(length)
                    try:
                        body = json.loads(raw) if raw else {}
                    except json.JSONDecodeError:
                        self._send_json(400, {"error": "Invalid JSON body"})
                        return
                    result = server_self._execute_tool(parts[1], parts[2], body)
                    self._send_json(200, result)
                else:
                    self._send_json(404, {"error": "Not found"})

        httpd = http.server.HTTPServer((host, port), _Handler)
        print(f"[skill-native-sdk REST] Listening on http://{host}:{port}")
        print(f"  GET  http://{host}:{port}/skills")
        print(f"  POST http://{host}:{port}/skills/{{skill}}/{{tool}}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[skill-native-sdk REST] Shutting down.")
            httpd.shutdown()

    # ── Public entrypoint ─────────────────────────────────────────────────────

    def serve(self, host: str = "127.0.0.1", port: int = 8000, backend: str = "auto") -> None:
        """Start the REST server.

        Args:
            host:    Bind address (default ``127.0.0.1``).
            port:    Listen port (default ``8000``).
            backend: ``"auto"`` (try FastAPI, fall back to stdlib),
                     ``"fastapi"``, or ``"stdlib"``.
        """
        if backend == "fastapi":
            self._serve_fastapi(host, port)
        elif backend == "stdlib":
            self._serve_stdlib(host, port)
        else:  # auto
            try:
                import fastapi  # noqa: F401
                import uvicorn  # noqa: F401
                self._serve_fastapi(host, port)
            except ImportError:
                self._serve_stdlib(host, port)
