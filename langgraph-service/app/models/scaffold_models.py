from pydantic import BaseModel
from typing import List, Dict, Any


class SingleTicketInput(BaseModel):
    ticket: Dict[str, Any]
    architecture: Dict[str, Any]
    data_models: Dict[str, Any]
    generated_so_far: List[str] = []
    repo_tree_snapshot: List[str] = []


class GeneratedFile(BaseModel):
    file_path: str
    content: str
    imports_needed: List[str] = []
    todos: List[str] = []