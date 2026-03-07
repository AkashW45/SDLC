import os
import subprocess
import tempfile
import shutil
import time


# ------------------------------
# Utilities
# ------------------------------

def safe_rmtree(path, retries=5, delay=0.5):
    for _ in range(retries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(delay)
    shutil.rmtree(path, ignore_errors=True)


def run_git(cmd: list, cwd: str):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(result.stderr.strip())

    return result.stdout.strip()


def normalize_content(content: str) -> str:
    lines = content.splitlines()
    cleaned = "\n".join(line.rstrip() for line in lines)
    return cleaned.strip() + "\n"


# ------------------------------
# Core Logic
# ------------------------------

def push_files_to_repo(
    repo_url: str,
    branch_name: str,
    files: list,
    commit_message: str
):
    temp_dir = tempfile.mkdtemp()

    try:
        # Clone fresh
        run_git(["git", "clone", repo_url, "."], cwd=temp_dir)

        # Fetch latest
        run_git(["git", "fetch", "--all"], cwd=temp_dir)

        remote_branches = run_git(["git", "branch", "-r"], cwd=temp_dir)
        branch_exists = f"origin/{branch_name}" in remote_branches

        if branch_exists:
            run_git(["git", "checkout", branch_name], cwd=temp_dir)
            run_git(["git", "pull", "origin", branch_name], cwd=temp_dir)
        else:
            run_git(["git", "checkout", "-b", branch_name], cwd=temp_dir)

        # Ensure git identity
        run_git(["git", "config", "user.email", "ai@bot.com"], cwd=temp_dir)
        run_git(["git", "config", "user.name", "AI Bot"], cwd=temp_dir)

        files_written = 0

        # Deterministic file writing
        for file in files:
            path = os.path.join(temp_dir, file["file_path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)

            normalized = normalize_content(file["content"])

            # If file exists, compare before overwriting
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as existing:
                    existing_content = normalize_content(existing.read())

                if existing_content == normalized:
                    continue  # skip identical file

            with open(path, "w", encoding="utf-8") as f:
                f.write(normalized)

            files_written += 1

        # Check git status
        status = run_git(["git", "status", "--porcelain"], cwd=temp_dir)
        print("---- GIT STATUS ----")
        print(status)
        print("---------------------")
        if not status:
            return {
                "status": "NO_CHANGES",
                "branch": branch_name,
                "message": "Files already up to date"
            }

        
        # Commit + push
        run_git(["git", "add", "."], cwd=temp_dir)
        run_git(["git", "commit", "-m", commit_message], cwd=temp_dir)
        run_git(["git", "push", "origin", branch_name, "--force"], cwd=temp_dir)

        return {
            "status": "PUSH_SUCCESS",
            "branch": branch_name,
            "files_pushed": files_written
        }

    finally:
        safe_rmtree(temp_dir)