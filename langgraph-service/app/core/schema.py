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


   

from typing import Literal

class ArchitectureNode(BaseModel):
    id: str
    name: str
    type: Literal["service", "database", "external", "edge", "pci", "infra"]
    zone: Literal["external", "dmz", "core", "pci", "observability"]

class ArchitectureEdge(BaseModel):
    source: str
    target: str
    protocol: str  # REST | gRPC | Kafka | JDBC etc.

class ArchitectureGraph(BaseModel):
    nodes: List[ArchitectureNode]
    edges: List[ArchitectureEdge]    

class ExpansionOutput(BaseModel):
    prd: PRD
    architecture: List[ArchitectureComponent]
    architecture_graph: ArchitectureGraph   # <-- ADD THIS
    security_requirements: List[SecurityRequirement]
    compliance_tags: List[str]
    risk_score: float | None = None
    threats: List[Threat] = []