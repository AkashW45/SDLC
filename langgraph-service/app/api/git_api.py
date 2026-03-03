from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict
import os
import subprocess
import tempfile
import shutil

router = APIRouter()


class PushRequest(BaseModel):
    files: List[Dict]
    repo_url: str
    branch_name: str


@router.post("/sdlc/push-github")
def push_to_github(data: PushRequest):

    temp_dir = tempfile.mkdtemp()

    try:
        subprocess.run(["git", "clone", data.repo_url, temp_dir], check=True)

        os.chdir(temp_dir)

        subprocess.run(["git", "checkout", "-b", data.branch_name], check=True)

        for file in data.files:
            path = os.path.join(temp_dir, file["file_path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(file["content"])

        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "AI scaffold generation"], check=True)
        subprocess.run(["git", "push", "origin", data.branch_name], check=True)

        return {"status": "PUSH_SUCCESS"}

    finally:
        shutil.rmtree(temp_dir)