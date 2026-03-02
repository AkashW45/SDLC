from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from .schema import PRD
from .sdlc_service import generate_architecture_from_prd
from .sdlc_service import canonicalize_prd
from .diagram_generator import generate_mermaid_from_architecture
from .diagram_renderer import render_mermaid_to_png
from .sdlc_service import generate_blueprint, generate_prd_from_blueprint

router = APIRouter()


class RequirementInput(BaseModel):
    requirement: str


class ApprovalInput(BaseModel):
    blueprint: dict
    comments: Optional[str] = None


class PRDDiagramInput(BaseModel):
    prd: dict
    brd: Optional[dict] = None


PRDDiagramInput.model_rebuild()


@router.post("/sdlc/start")
def start_sdlc(req: RequirementInput):
    blueprint = generate_blueprint(req.requirement)
    return {
        "status": "BRD_GENERATED",
        "blueprint": blueprint
    }


@router.post("/sdlc/prd")
def generate_prd(data: ApprovalInput):
    prd = generate_prd_from_blueprint(data.blueprint)
    return {
        "status": "PRD_GENERATED",
        "prd": prd
    }


@router.post("/sdlc/prd/diagram")
def prd_diagram(data: PRDDiagramInput):
    canonical = canonicalize_prd(data.prd, data.brd or {})
    architecture = generate_architecture_from_prd(canonical)
    mermaid = generate_mermaid_from_architecture(architecture)
    png_bytes = render_mermaid_to_png(mermaid)
    return Response(content=png_bytes, media_type="image/png")