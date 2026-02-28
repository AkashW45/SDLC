from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
load_dotenv()

from pydantic import BaseModel
from .graph import build_graph

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
graph = build_graph()

class RequirementInput(BaseModel):
    requirement: str

@app.post("/expand")
async def expand(req: RequirementInput):
    result = graph.invoke({"requirement": req.requirement})
    return result