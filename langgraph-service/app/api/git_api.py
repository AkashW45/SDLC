import time
import os
import subprocess
import tempfile
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter()


# -----------------------------
# Request Model
# -----------------------------
class PushRequest(BaseModel):
    files: List[Dict]
    repo_url: str
    branch_name: str
    commit_message: str = "AI scaffold generation"


# -----------------------------
# Utilities
# -----------------------------
def safe_rmtree(path, retries=5, delay=0.5):
    """
    Windows-safe directory cleanup.
    Retries deletion to avoid file lock race conditions.
    """
    for _ in range(retries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(delay)
    shutil.rmtree(path, ignore_errors=True)


def run_git(cmd: list, cwd: str):
    """
    Executes git command safely and returns stdout.
    Raises exception if command fails.
    """
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(result.stderr.strip())

    return result.stdout.strip()


# -----------------------------
# Main Endpoint
# -----------------------------
@router.post("/sdlc/push-github")
def push_to_github(data: PushRequest):

    temp_dir = tempfile.mkdtemp()

    try:
        # Clone into temp directory
        run_git(["git", "clone", data.repo_url, "."], cwd=temp_dir)

        # Ensure latest remote refs
        run_git(["git", "fetch", "--all"], cwd=temp_dir)

        # Check if branch exists remotely
        remote_branches = run_git(["git", "branch", "-r"], cwd=temp_dir)

        branch_exists = f"origin/{data.branch_name}" in remote_branches

        if branch_exists:
            # Checkout existing branch
            run_git(["git", "checkout", data.branch_name], cwd=temp_dir)
            run_git(["git", "pull", "origin", data.branch_name], cwd=temp_dir)
        else:
            # Create new branch
            run_git(["git", "checkout", "-b", data.branch_name], cwd=temp_dir)

        # Write files (overwrite = idempotent)
        for file in data.files:
            path = os.path.join(temp_dir, file["file_path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(file["content"])

        # Check if any changes occurred
        status = run_git(["git", "status", "--porcelain"], cwd=temp_dir)

        if not status:
            return {
                "status": "NO_CHANGES",
                "branch": data.branch_name,
                "message": "Files already up to date"
            }

        # Commit and push changes
        run_git(["git", "add", "."], cwd=temp_dir)
        run_git(
            ["git", "commit", "-m", data.commit_message],
            cwd=temp_dir
        )
        run_git(
            ["git", "push", "origin", data.branch_name],
            cwd=temp_dir
        )

        return {
            "status": "PUSH_SUCCESS",
            "branch": data.branch_name,
            "files_pushed": len(data.files)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        safe_rmtree(temp_dir)