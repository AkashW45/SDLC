import os
import subprocess
import tempfile
import shutil
import json
import re
from app.services.sdlc_service import call_llm
from app.services.git_service import push_files_to_repo


# -----------------------------------------
# Git Utilities
# -----------------------------------------

def clone_repo(repo_url: str, branch_name: str) -> str:
    temp_dir = tempfile.mkdtemp()

    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch_name, repo_url, "."],
        cwd=temp_dir,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Git clone failed: {result.stderr}")

    return temp_dir


def find_file_for_ticket(repo_path: str, ticket_id: str, file_patches: list = None) -> str:
    """
    Use file_patches from PR diff directly instead of sdlc_manifest.json
    """
    if file_patches:
        # Return first non-test, non-config Python file from patches
        for f in file_patches:
            fname = f.get("filename", "")
            if fname.endswith(".py") and "test_" not in fname and fname not in [
                "setup.py", "conftest.py"
            ]:
                full_path = os.path.join(repo_path, fname)
                return full_path
        # Fallback - return first patched file
        if file_patches:
            return os.path.join(repo_path, file_patches[0].get("filename", ""))
    
    # Last resort fallback - don't crash
    return repo_path


# -----------------------------------------
# LLM Test Generation
# -----------------------------------------

def generate_test_file(source_code, acceptance_criteria, file_path):

    system_prompt = """
You are a strict QA automation engineer.

Rules:
1. Convert each acceptance criterion into explicit pytest assertions.
2. Every acceptance criterion MUST be reflected in at least one assertion.
3. Do NOT infer expected values from source code.
4. Acceptance criteria take priority over implementation.
5.Testing framework rules:

- Use pytest.
- Use fastapi.testclient.TestClient for API tests.
- Do NOT use httpx.AsyncClient.
- Do NOT use async test functions unless absolutely required.
- Prefer synchronous pytest tests using TestClient.
6. Return JSON only:

{
  "file_path": "tests/test_xxx.py",
  "content": "valid pytest code"
}
"""

    user_prompt = f"""
Source File Path:
{file_path}

Source Code:
{source_code}

Acceptance Criteria:
{json.dumps(acceptance_criteria, indent=2)}
"""

    response = call_llm(system_prompt, user_prompt)

    if isinstance(response, str):
        response = json.loads(response)

    return response


# -----------------------------------------
# Serialization Safety Layer
# -----------------------------------------

def normalize_llm_content(content: str) -> str:
    """
    Ensures escaped newlines from JSON transport are converted properly.
    Does NOT alter logic.
    """
    if not isinstance(content, str):
        return content

    if "\\n" in content:
        try:
            content = content.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    return content


# -----------------------------------------
# Pytest Execution + Coverage
# -----------------------------------------

def run_pytest(repo_path: str) -> dict:
    env = os.environ.copy()

    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo_path + os.pathsep + existing_path

    result = subprocess.run(
        ["pytest", "--cov=app", "--cov-report=term"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        env=env
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


def extract_coverage(pytest_stdout: str):
    """
    Extract TOTAL coverage percentage from pytest output.
    """
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", pytest_stdout)
    if match:
        return int(match.group(1))
    return None


# -----------------------------------------
# Main Orchestration
# -----------------------------------------

def generate_and_run_tests(data):

    repo_path = clone_repo(data.repo_url, data.branch_name)
    conftest_path = os.path.join(repo_path, "conftest.py")
    with open(conftest_path, "w") as f:
         f.write("import sys, os\n")
         f.write("sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'langgraph-service'))\n")

    pytest_ini = os.path.join(repo_path, "pytest.ini")
    with open(pytest_ini, "w") as f:
         f.write("[pytest]\ntestpaths = tests\n")

    try:
        source_file_path = find_file_for_ticket(repo_path, data.ticket_id,data.file_patches or [])

        with open(os.path.join(repo_path, source_file_path), "r", encoding="utf-8") as f:
            source_code = f.read()

        test_result = generate_test_file(
            source_code,
            data.acceptance_criteria,
            source_file_path
        )

        test_file_path = test_result["file_path"]
        test_content = normalize_llm_content(test_result["content"])

        full_test_path = os.path.join(repo_path, test_file_path)
        os.makedirs(os.path.dirname(full_test_path), exist_ok=True)

        # -----------------------------
        # Idempotency Gate
        # -----------------------------
        if os.path.exists(full_test_path):
            return {
                "status": "TEST_ALREADY_EXISTS",
                "ticket_id": data.ticket_id,
                "test_file": test_file_path
            }

        # Write test file locally
        with open(full_test_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        # -----------------------------
        # Execute Tests
        # -----------------------------
        pytest_output = run_pytest(repo_path)
        coverage_percent = extract_coverage(pytest_output["stdout"])

        # -----------------------------
        # Hard Verification Gate
        # -----------------------------
        if pytest_output["returncode"] != 0:
            return {
                "status": "TEST_FAILED",
                "ticket_id": data.ticket_id,
                "test_file": test_file_path,
                "coverage": coverage_percent,
                "pytest_result": pytest_output
            }

        # Optional coverage threshold (enterprise realism)
        MIN_COVERAGE = 70

        if coverage_percent is not None and coverage_percent < MIN_COVERAGE:
            return {
                "status": "COVERAGE_BELOW_THRESHOLD",
                "ticket_id": data.ticket_id,
                "test_file": test_file_path,
                "coverage": coverage_percent,
                "minimum_required": MIN_COVERAGE,
                "pytest_result": pytest_output
            }

        # -----------------------------
        # Push Only After Verification
        # -----------------------------
        push_files_to_repo(
            repo_url=data.repo_url,
            branch_name=data.branch_name,
            files=[{
                "file_path": test_file_path,
                "content": test_content
            }],
            commit_message=f"Add tests for {data.ticket_id}"
        )

        return {
            "status": "SPRINT_VERIFIED",
            "ticket_id": data.ticket_id,
            "test_file": test_file_path,
            "coverage": coverage_percent,
            "pytest_result": pytest_output
        }

    finally:
        shutil.rmtree(repo_path, ignore_errors=True)