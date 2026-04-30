from fastapi import APIRouter
from app.models.scaffold_models import SingleTicketInput
from app.services.scaffold_service import generate_file_for_ticket
import subprocess
import tempfile
import shutil
import os

router = APIRouter()


def read_repo_files(repo_url: str, branch_name: str) -> dict:
    temp_dir = tempfile.mkdtemp()
    files = {}
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch_name, repo_url, "."],
            cwd=temp_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[scaffold] Clone failed: {result.stderr}")
            return {}
        for root, dirs, filenames in os.walk(temp_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")
                      and d not in ("__pycache__", "node_modules", "venv")]
            for file in filenames:
                if file.endswith((".py", ".json", ".yaml", ".yml")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, temp_dir)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            files[rel_path] = f.read()
                    except:
                        pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return files


@router.post("/sdlc/scaffold/ticket")
def scaffold_single_ticket(data: SingleTicketInput):

    existing_file_contents = {}
    if data.repo_url:
        try:
            existing_file_contents = read_repo_files(
                data.repo_url,
                "main"
            )
            print(f"[scaffold] Read {len(existing_file_contents)} files for AST")
        except Exception as e:
            print(f"[scaffold] Could not read repo: {e}")

    result = generate_file_for_ticket(
        ticket=data.ticket,
        architecture=data.architecture,
        data_models=data.data_models,
        repo_tree=data.repo_tree_snapshot,
        generated_files=data.generated_so_far,
        existing_file_contents=existing_file_contents
    )

    ast_report = None
    if isinstance(result, dict):
        ast_report = result.pop("ast_report", None)

    return {
        "status": "FILE_GENERATED",
        "ticket_id": data.ticket.get("id"),
        "file": result,
        "ast_report": ast_report
    }