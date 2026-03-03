import json
from app.services.sdlc_service import call_llm


def detect_layer(ticket: dict) -> str:
    labels = ticket.get("fields", {}).get("labels", [])

    if "frontend" in labels:
        return "frontend"
    if "backend" in labels:
        return "backend"

    # fallback based on summary keywords
    summary = ticket.get("fields", {}).get("summary", "").lower()

    if "ui" in summary or "form" in summary:
        return "frontend"

    return "backend"


def generate_file_for_ticket(ticket, architecture, data_models, repo_tree, generated_files):

    layer = detect_layer(ticket)

    system_prompt = """
You are a senior software engineer.

Generate ONE complete file for this ticket.

Rules:
- Use only provided architecture and models
- Do not invent new models
- Add TODO comments for acceptance criteria
- No syntax errors
- Return JSON only
"""

    user_prompt = f"""
Ticket:
{json.dumps(ticket, indent=2)}

Architecture:
{json.dumps(architecture, indent=2)}

Data Models:
{json.dumps(data_models, indent=2)}

Existing Files:
{json.dumps(repo_tree, indent=2)}

Already Generated Files:
{json.dumps(generated_files, indent=2)}

Return:
{{
  "file_path": "...",
  "content": "...",
  "imports_needed": [],
  "todos": []
}}
"""

    response = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)

    return response