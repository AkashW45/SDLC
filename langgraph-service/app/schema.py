from pydantic import BaseModel, Field
from typing import List, Dict

class SecurityRequirement(BaseModel):
    id: str
    description: str
    severity: str  # low | medium | high

class ArchitectureComponent(BaseModel):
    name: str
    type: str
    description: str

class PRD(BaseModel):
    title: str
    summary: str
    functional_requirements: List[str]
    non_functional_requirements: List[str]
    assumptions: List[str]

class Threat(BaseModel):
    category: str
    description: str
    severity: str

from pydantic import BaseModel
from typing import List, Optional, Literal


class DiagramNode(BaseModel):
    id: str
    label: str


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None


class DiagramMetadata(BaseModel):
    direction: Literal["LR", "TB"]
    nodes: List[DiagramNode]
    edges: List[DiagramEdge]    

class ExpansionOutput(BaseModel):
    prd: PRD
    architecture: List[ArchitectureComponent]
    security_requirements: List[SecurityRequirement]
    compliance_tags: List[str]
    risk_score: float | None = None
    threats: List[Threat] = []