from fastapi import FastAPI
from dotenv import load_dotenv
import os
load_dotenv()

from pydantic import BaseModel
from .graph import build_graph

app = FastAPI()
graph = build_graph()

class RequirementInput(BaseModel):
    requirement: str

@app.post("/expand")
async def expand(req: RequirementInput):
    result = graph.invoke({"requirement": req.requirement})
    return result