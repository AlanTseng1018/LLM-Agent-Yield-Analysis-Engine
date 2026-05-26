from __future__ import annotations
import os
import sys
import json
import logging

# ensure backend/app is on the path so sub-packages import correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx

# =========================
# basic configuration
# =========================
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
DEBUG_LOG_DEFAULT = os.getenv("DEBUG_LOG", "0") == "1"
DEBUG_PRINT_LIMIT = int(os.getenv("DEBUG_PRINT_LIMIT", "8000"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# =========================
# color setting
# =========================

class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Color.RESET}"

def _is_debug(req: Request) -> bool:
    if req.query_params.get("debug") in ("1", "true", "True"):
        return True
    if req.headers.get("X-Debug") in ("1", "true", "True"):
        return True
    return DEBUG_LOG_DEFAULT

def _clip(s: str) -> str:
    if not isinstance(s, str): return s
    if len(s) > DEBUG_PRINT_LIMIT:
        return s[:DEBUG_PRINT_LIMIT] + f"\n... [truncated, total={len(s)} chars]"
    return s

# =========================
# FastAPI 初始化
# =========================
app = FastAPI(title="Ollama Stream Chat Backend", version="1.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

SYSTEM_PROMPT = """
You are an action-capable reasoning assistant.
When the user asks for data sample / chart / plot / distribution / visualization:
1) Answer normally in natural language.
2) Export data as JSON format like below:
If I ask "yield data", please provide simulated yield / day data with 30 point for me
Standard 1D chart format:
```json
<<CHART_DATA>>
{
  "chart_type": "line",
  "title": "Chart title",
  "x_key": "x",
  "y_keys": ["value"],
  "data": [
    { "x": "A", "value": 10 },
    { "x": "B", "value": 20 },
    { "x": "C", "value": 15 }
  ]
}
<<END_CHART_DATA>>
```
"""

def ensure_system_prompt(msgs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    # ✅ 不管前端送不送 system，一律以後端 SYSTEM_PROMPT 為準
    if msgs and msgs[0].get("role") == "system":
        msgs = msgs[:]  # copy
        msgs[0] = {"role": "system", "content": SYSTEM_PROMPT}
        return msgs
    return [{"role": "system", "content": SYSTEM_PROMPT}, *msgs]
# =========================
# 串流處理主體
# =========================
async def _ndjson_stream(upstream_body: Dict[str, Any], debug: bool) -> AsyncGenerator[bytes, None]:
    timeout = httpx.Timeout(None)
    headers = {"Content-Type": "application/json"}

    if debug:
        print(colorize(">>> [DEBUG] Upstream request body:", Color.CYAN), flush=True)
        print(_clip(json.dumps(upstream_body, ensure_ascii=False, indent=2)), flush=True)

    # 暫存完整內容
    thinking_full, content_full = [], []

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", OLLAMA_CHAT_URL, headers=headers, json=upstream_body) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = await resp.aread()
                print(colorize("<<< [ERROR]", Color.RED), _clip(detail.decode(errors="ignore")), flush=True)
                yield (json.dumps({"type": "error", "detail": detail.decode(errors="ignore")}) + "\n").encode()
                return

            last_meta: Dict[str, Any] = {}
            async for line in resp.aiter_lines():
                if not line: continue
                if debug:
                    print(colorize("<<< [RAW LINE]", Color.YELLOW), _clip(line), flush=True)

                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                msg = obj.get("message") or {}
                # 🧠 Thinking
                if msg.get("thinking"):
                    segment = msg["thinking"]
                    thinking_full.append(segment)
                    print(colorize("🧠 THINKING:", Color.MAGENTA), segment, flush=True)
                    yield (json.dumps({"type": "thinking", "content": segment}) + "\n").encode()

                # 💬 Content
                if msg.get("content"):
                    segment = msg["content"]
                    content_full.append(segment)
                    print(colorize("💬 OUTPUT:", Color.GREEN), segment, flush=True)
                    yield (json.dumps({"type": "delta", "content": segment}) + "\n").encode()

                if obj.get("done"):
                    last_meta = {"total_duration": obj.get("total_duration"), "eval_count": obj.get("eval_count")}
                    break

    # ✅ 完成後整合印出
    if debug:
        print(colorize("\n========== FINAL SUMMARY ==========", Color.BOLD + Color.CYAN), flush=True)
        if thinking_full:
            print(colorize("🧠 Full Thinking:", Color.MAGENTA), "".join(thinking_full).strip(), flush=True)
        if content_full:
            print(colorize("💬 Full Answer:", Color.GREEN), "".join(content_full).strip(), flush=True)
        print(colorize("===================================", Color.BOLD + Color.CYAN), flush=True)

    yield (json.dumps({
        "type": "done",
        "meta": last_meta,
        "thinking_full": "".join(thinking_full),
        "content_full": "".join(content_full)
    }) + "\n").encode()

# =========================
# API: 串流聊天
# =========================
@app.post("/chat/stream")
async def chat_stream(req: Request):
    debug = _is_debug(req)
    payload = await req.json()
    messages = ensure_system_prompt(payload.get("messages", []))

    model = payload.get("model", "qwen3:8b")
    options = payload.get("options") or {"num_ctx": 8192}
    keep_alive = payload.get("keep_alive")

    upstream_body = {"model": model, "messages": messages, "stream": True, "options": options}
    if keep_alive is not None:
        upstream_body["keep_alive"] = keep_alive

    if debug:
        print(colorize(f"[DEBUG] Stream start for model={model}", Color.BOLD + Color.CYAN), flush=True)

    return StreamingResponse(_ndjson_stream(upstream_body, debug), media_type="application/x-ndjson")

@app.get("/health")
async def health():
    return {"ok": True}


# ── Agent mode router ─────────────────────────────────────────────────────
AGENT_KEYWORDS = [
    "分析", "analyze", "wafer", "sample", "plot", "圖", "map",
    "yield", "良率", "bin", "pin", "pass", "fail", "defect",
]

def _needs_agent(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in AGENT_KEYWORDS)


# =========================
# API: Agent Plan + Stream
# =========================
@app.post("/agent/stream")
async def agent_stream(req: Request):
    from mcp_client.client import list_tools
    from agent.react import run_react_agent

    debug = _is_debug(req)
    payload = await req.json()
    messages = payload.get("messages", [])
    model    = payload.get("model", "qwen3:8b")
    options  = payload.get("options") or {"num_ctx": 8192}

    user_message = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    def _fallback_stream():
        upstream = {
            "model": model,
            "messages": ensure_system_prompt(messages),
            "stream": True,
            "options": options,
        }
        return _ndjson_stream(upstream, debug)

    async def generate() -> AsyncGenerator[bytes, None]:

        # ── Router: skip agent for non-analysis messages ───────────────────
        if not _needs_agent(user_message):
            print(colorize(f"[ROUTER] normal chat: {user_message[:40]}", Color.GREEN), flush=True)
            async for chunk in _fallback_stream():
                yield chunk
            return

        print(colorize(f"[ROUTER] agent mode: {user_message[:40]}", Color.CYAN), flush=True)

        # ── MCP connectivity probe (fall back to plain chat if unreachable) ─
        try:
            tools = await list_tools()
            print(colorize(f"[AGENT] MCP tools: {[t['name'] for t in tools]}", Color.CYAN), flush=True)
        except Exception as e:
            import traceback
            print(colorize(f"[AGENT] MCP unreachable: {e}", Color.RED), flush=True)
            print(traceback.format_exc(), flush=True)
            async for chunk in _fallback_stream():
                yield chunk
            return

        # ── Run the ReAct agent loop ───────────────────────────────────────
        async for chunk in run_react_agent(user_message, model=model):
            yield chunk


    return StreamingResponse(generate(), media_type="application/x-ndjson")


# =========================
# API: list available Ollama models (proxied so the frontend stays same-origin)
# =========================
@app.get("/api/models")
async def list_models():
    """Return Ollama's installed models. No filtering — the user picks."""
    url = OLLAMA_CHAT_URL.replace("/api/chat", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5)) as client:
            r = await client.get(url)
            r.raise_for_status()
        models = r.json().get("models", [])
        # Compact shape: [{name, size, modified_at}, ...]
        return {
            "models": [
                {
                    "name": m.get("name"),
                    "size": m.get("size"),
                    "modified_at": m.get("modified_at"),
                }
                for m in models
            ]
        }
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"models": [], "error": f"Ollama unreachable: {e}"},
        )


# =========================
# API: download a report folder as a zip
# =========================
@app.get("/report/{report_id}/download")
async def download_report(report_id: str):
    import io
    import zipfile
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import Response
    from agent.config import REPORTS_DIR

    # basename() strips any path-traversal — the folder stays under REPORTS_DIR
    safe_id = os.path.basename(report_id)
    folder = Path(REPORTS_DIR) / safe_id
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail=f"Report not found: {safe_id}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder.parent))
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_id}.zip"'},
    )


# =========================
# API: serve a file from a report folder (for the in-app preview panel)
# =========================
@app.get("/report/{report_id}/files/{file_path:path}")
async def report_file(report_id: str, file_path: str):
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from agent.config import REPORTS_DIR

    safe_id = os.path.basename(report_id)
    base = (Path(REPORTS_DIR) / safe_id).resolve()
    target = (base / file_path).resolve()
    # path-traversal guard: the resolved target must stay inside the report folder
    if base not in target.parents and target != base:
        raise HTTPException(status_code=403, detail="forbidden")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(target)


# =========================
# Static: serve the built frontend (one-command production mode)
# =========================
# Mounted LAST so every API route above wins. With html=True, SPA paths
# fall back to index.html. In dev mode `frontend/dist/` won't exist and
# Vite serves the UI on :5173 instead — this mount silently no-ops.
_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend", "dist",
)
if os.path.isdir(_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="debug")
