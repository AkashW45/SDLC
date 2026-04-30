import ast
import json
from app.services.sdlc_service import call_llm


# -----------------------------------------
# Layer Detection
# -----------------------------------------

def detect_layer(ticket: dict) -> str:
    labels = ticket.get("fields", {}).get("labels", [])

    if "frontend" in labels:
        return "frontend"
    if "backend" in labels:
        return "backend"

    summary = ticket.get("fields", {}).get("summary", "").lower()

    if "ui" in summary or "form" in summary:
        return "frontend"

    return "backend"


# -----------------------------------------
# AST Parser
# -----------------------------------------

def extract_ast_summary(file_content: str, file_path: str) -> dict:
    if not file_path.endswith(".py"):
        return {
            "file_type": file_path.split(".")[-1] if "." in file_path else "unknown",
            "preview": file_content[:300] if file_content else ""
        }

    try:
        tree = ast.parse(file_content)

        summary = {
            "classes": [],
            "functions": [],
            "imports": [],
            "routes": []
        }

        for node in ast.walk(tree):

            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in ast.walk(node)
                    if isinstance(n, ast.FunctionDef)
                ]
                summary["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "line": node.lineno
                })

            elif isinstance(node, ast.FunctionDef):
                summary["functions"].append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "line": node.lineno,
                    "decorators": [
                        ast.unparse(d) for d in node.decorator_list
                    ] if node.decorator_list else []
                })

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    summary["imports"].append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [a.name for a in node.names]
                summary["imports"].append(f"from {module} import {names}")

        for fn in summary["functions"]:
            for dec in fn.get("decorators", []):
                if any(method in dec for method in [
                    ".get(", ".post(", ".put(", ".delete(", ".patch("
                ]):
                    summary["routes"].append({
                        "function": fn["name"],
                        "decorator": dec
                    })

        return summary

    except SyntaxError as e:
        return {
            "parse_error": str(e),
            "preview": file_content[:300] if file_content else ""
        }


# -----------------------------------------
# Main File Generator
# -----------------------------------------

def generate_file_for_ticket(
    ticket,
    architecture,
    data_models,
    repo_tree,
    generated_files,
    existing_file_contents: dict = {}
):
    layer = detect_layer(ticket)

    # Build AST summaries from existing file contents
    ast_summaries = {}
    for file_path, content in existing_file_contents.items():
        if content:
            ast_summaries[file_path] = extract_ast_summary(content, file_path)

    # Build AST report for proof
    ast_report = {
        "ast_ran": True,
        "files_analyzed": list(ast_summaries.keys()),
        "total_files_read": len(ast_summaries),
        "summary": ast_summaries
    }

    system_prompt = """
You are a senior software engineer adding a new feature to an existing codebase.

You will receive AST summaries of existing files showing all classes, functions and routes.

YOUR JOB:
- Analyse the AST summaries to understand what already exists
- Identify WHICH existing files need to be modified for the new feature
- If modifying an existing file, return the COMPLETE updated file content
- If creating a new file, make sure it integrates with existing code

STRICT RULES:
- Do NOT duplicate existing classes or functions shown in AST
- Do NOT create a new file if the feature belongs in an existing file
- If adding a route, add it to the existing routes file
- If adding a model field, modify the existing models file
- Always return the complete file content, not just the changes
- Add TODO comments for acceptance criteria
- No syntax errors
- Return ONLY valid JSON
"""

    ast_section = ""
    if ast_summaries:
        ast_section = f"""
Existing Codebase Structure (AST summaries — understand before generating):
{json.dumps(ast_summaries, indent=2)}
"""

    user_prompt = f"""
Ticket:
{json.dumps(ticket, indent=2)}

Architecture:
{json.dumps(architecture, indent=2)}

Data Models:
{json.dumps(data_models, indent=2)}

Existing Files (paths only):
{json.dumps(repo_tree, indent=2)}
{ast_section}
Already Generated Files (this session):
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

    # Attach AST report to response as proof
    if isinstance(response, dict):
        response["ast_report"] = ast_report

    return response