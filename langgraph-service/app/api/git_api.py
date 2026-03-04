from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from app.services.git_service import push_files_to_repo

router = APIRouter()


class PushRequest(BaseModel):
    repo_url: str
    branch_name: str
    files: List[Dict]
    commit_message: str = "AI scaffold generation"


@router.post("/sdlc/push-github")
def push_to_github(data: PushRequest):
    try:
        return push_files_to_repo(
            repo_url=data.repo_url,
            branch_name=data.branch_name,
            files=data.files,
            commit_message=data.commit_message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))