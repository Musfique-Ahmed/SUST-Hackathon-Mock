"""FastAPI entrypoint for the CRM Ticket Sorting service.

Endpoints
---------
GET  /health            -> liveness probe
POST /sort-ticket       -> structured classification of one CRM ticket
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .classifier import classify
from .schemas import HealthResponse, SortTicketRequest, SortTicketResponse

app = FastAPI(
    title="CRM Ticket Sorting Service",
    version="1.0.0",
    description=(
        "Reads one customer support message and returns a structured "
        "classification: case_type, severity, department, summary, "
        "human-review flag, and confidence."
    ),
)

# CORS so browser-based test harnesses can hit the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe. Returns within milliseconds."""
    return HealthResponse(status="ok")


@app.post("/sort-ticket", response_model=SortTicketResponse)
def sort_ticket(payload: SortTicketRequest) -> SortTicketResponse:
    """Classify a single CRM ticket and return the spec'd response shape."""
    result = classify(payload.message)
    return SortTicketResponse(
        ticket_id=payload.ticket_id,
        case_type=result.case_type,
        severity=result.severity,
        department=result.department,
        agent_summary=result.agent_summary,
        human_review_required=result.human_review_required,
        confidence=result.confidence,
    )