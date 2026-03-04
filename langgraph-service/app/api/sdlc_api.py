from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from typing import Dict
from app.core.schema import PRD
from app.services.sdlc_service import generate_architecture_from_prd
from app.services.sdlc_service import canonicalize_prd
from app.models.diagram_generator import generate_mermaid_from_architecture
from app.models.diagram_renderer import render_mermaid_to_png
from app.services.sdlc_service import generate_blueprint, generate_prd_from_blueprint, build_sprint_plan, wrap_tickets_with_adf
from app.core.jira_client import fetch_jira_metadata
from app.models.scaffold_models import SprintExecutionRequest
from app.services.sprint_executor import execute_sprint

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



class SprintPlanInput(BaseModel):
    prd: dict
    project_key: str = "DEV"




@router.post("/sdlc/sprint-plan")
def generate_sprint_plan(data: SprintPlanInput):

    # Step 1: canonicalize PRD
    canonical = canonicalize_prd(data.prd, {})

    # Step 2: generate architecture
    architecture = generate_architecture_from_prd(canonical)

    # Step 3: fetch Jira metadata internally
    jira_meta = fetch_jira_metadata(data.project_key)

    # Step 4: build sprint plan
    sprint_plan = build_sprint_plan(
    canonical,
    architecture,
    jira_meta,
    data.project_key
    )

    sprint_plan = wrap_tickets_with_adf(sprint_plan)

    return {
    "status": "SPRINT_PLAN_GENERATED",
    "sprint_plan": sprint_plan
}




@router.post("/sdlc/execute-sprint")
def execute_full_sprint(data: SprintExecutionRequest):
    return execute_sprint(data)