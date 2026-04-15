from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timezone
import os, json, httpx

router = APIRouter()

# NEW - replace with this
import sqlite3

DB_PATH = "pipeline_state.db"
_render_cache: dict = {}  # keep this in-memory, it's just HTML cache

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stages (
            stage TEXT PRIMARY KEY,
            status TEXT,
            data TEXT,
            resume_url TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def _save_stage(stage: str, status: str, data: any, resume_url: str, timestamp: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO stages VALUES (?,?,?,?,?)",
        (stage, status, json.dumps(data), resume_url or "", timestamp)
    )
    conn.commit()
    conn.close()

def _load_all_stages() -> dict:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM stages").fetchall()
    conn.close()
    return {
        r[0]: {
            "status": r[1],
            "data": json.loads(r[2]) if r[2] else None,
            "resumeUrl": r[3],
            "timestamp": r[4]
        }
        for r in rows
    }

_init_db()  # runs once on startup

STAGE_LABELS = {
    "brd":          "Business Requirements Document",
    "prd":          "Product Requirements Document",
    "architecture": "System Architecture",
    "sprint_plan":  "Sprint Plan",
    "scaffold":     "Scaffold / Generated Code",
    "test_results": "Test Results"
}


class StagePayload(BaseModel):
    stage: str
    data: Any
    resumeUrl: Optional[str] = ""


class RenderRequest(BaseModel):
    stage: str
    data: Any


# REPLACE receive_stage_output
@router.post("/dashboard/stage")
def receive_stage_output(payload: StagePayload):
    if payload.stage in _render_cache:
        del _render_cache[payload.stage]

    _save_stage(
        stage=payload.stage,
        status="pending",
        data=payload.data,
        resume_url=payload.resumeUrl or "",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    print(f"[DASHBOARD] Stage '{payload.stage}' received and persisted")
    return {"ok": True, "stage": payload.stage}


# REPLACE get_dashboard_state
@router.get("/dashboard/state")
def get_dashboard_state():
    return JSONResponse(content=_load_all_stages())


@router.post("/dashboard/render")
async def render_stage(req: RenderRequest):
    """
    Sends raw stage JSON to Groq (llama-3.3-70b / qwen-120b)
    and gets back clean readable HTML.
    Strict: only formats what is in the JSON — no additions.
    Cached per stage so AI is only called once per pipeline run.
    """
    if req.stage in _render_cache:
        return JSONResponse(content={"html": _render_cache[req.stage], "cached": True})

    stage_label = STAGE_LABELS.get(req.stage, req.stage.upper())
    data_str = json.dumps(req.data, indent=2)

    prompt = f"""Convert this {stage_label} JSON data into clean readable HTML for a human reviewer who will approve or reject this stage.

JSON DATA (this is the ONLY source — use nothing else):
{data_str}

STRICT RULES — this is an approval system, accuracy is critical:
1. Show EVERY field from the JSON — do not skip or hide anything
2. Do NOT add any text, labels, descriptions or content that is not in the JSON
3. Do NOT summarize, infer, explain or hallucinate anything beyond what the JSON literally says
4. Do NOT add fields that don't exist in the JSON
5. String values must be shown exactly as they appear — no paraphrasing
6. Numbers must be shown exactly as they are
7. Arrays — show every single item

FORMATTING (inline styles only, no <style> tags, no <script> tags):
- Dark theme background context: #0d1117
- Text: #e6edf3, secondary text: #8b949e
- Cards: background #161b22, border 1px solid #21262d, border-radius 8px, padding 14px, margin-bottom 10px
- Section titles: font-size 9px, letter-spacing 2px, text-transform uppercase, color #484f58, border-bottom 1px solid #21262d, padding-bottom 6px, margin-bottom 10px
- Green #00ff88 for: pass, success, approved, low priority, done
- Blue #0099ff for: IDs, references, info
- Orange #f0a500 for: Medium priority, warnings
- Red #ff4757 for: High priority, errors, failures, critical
- Gray #8b949e for: Low priority, neutral
- Priority/Status/Likelihood/Impact fields: inline badge (padding 2px 7px, border-radius 3px, font-weight 700, font-size 9px, text-transform uppercase)
- Arrays of strings: bullet list, each item with ▸ in #00ff88, font-size 12px, color #8b949e
- Arrays of objects: card grid (display grid, grid-template-columns repeat(auto-fill,minmax(260px,1fr)), gap 10px)
- Code/file content: <pre> tag, font-size 11px, background #1c2330, padding 12px, border-radius 5px, max-height 250px, overflow-y auto, white-space pre-wrap, word-break break-all, color #8b949e
- Numbers that are stats (coverage, total, passed, failed, score): font-size 26px, font-weight 800, font-family Syne sans-serif
- Coverage/percentage bars: div with background #1c2330, inner div with width=value%, height 6px, border-radius 3px, green if >=70 else red
- Font throughout: font-family 'JetBrains Mono', monospace
- Do NOT include <!DOCTYPE> <html> <head> <body> tags
- Return ONLY the inner HTML — no markdown, no code fences, no explanation

Convert now:"""

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return JSONResponse(content={"html": "<div style='color:#f0a500;padding:20px;font-family:monospace'>GROQ_API_KEY not set. Run: set GROQ_API_KEY=your_key</div>"})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-oss-120b",  # change to your preferred model
                    "max_tokens": 4000,
                    "temperature": 0,  # 0 = no creativity, just format what's there
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a JSON-to-HTML formatter. You format data exactly as given — no additions, no hallucinations. Return only raw HTML with inline styles."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            )
            result = resp.json()

            if "error" in result:
                return JSONResponse(content={"html": f"<div style='color:#ff4757;padding:20px;font-family:monospace'>Groq error: {result['error'].get('message','unknown')}</div>"})

            html = result["choices"][0]["message"]["content"]
            # Strip any accidental markdown fences
            html = html.replace("```html", "").replace("```", "").strip()

            # Cache it
            _render_cache[req.stage] = html
            return JSONResponse(content={"html": html, "cached": False})

    except Exception as e:
        return JSONResponse(content={"html": f"<div style='color:#ff4757;padding:20px;font-family:monospace'>Render error: {str(e)}</div>"})


@router.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    html_path = r"C:\Users\user\SDLC\langgraph-service\dashboard\sdlc-dashboard.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard HTML not found</h1>", status_code=404)