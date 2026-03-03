from fastapi import APIRouter
from app.models.scaffold_models import SingleTicketInput
from app.services.scaffold_service import generate_file_for_ticket

router = APIRouter()

@router.post("/sdlc/scaffold/ticket")
def scaffold_single_ticket(data: SingleTicketInput):

    result = generate_file_for_ticket(
        ticket=data.ticket,
        architecture=data.architecture,
        data_models=data.data_models,
        repo_tree=data.repo_tree_snapshot,
        generated_files=data.generated_so_far
    )

    return {
        "status": "FILE_GENERATED",
        "ticket_id": data.ticket.get("id"),
        "file": result
    }