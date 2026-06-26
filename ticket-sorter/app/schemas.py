"""Pydantic schemas for the Ticket Sorting service.

Request and response shapes match the public spec verbatim.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Request ---------------------------------------------------------------


class SortTicketRequest(BaseModel):
    """Inbound CRM ticket payload."""

    ticket_id: str = Field(..., min_length=1, description="Echoed back in the response")
    channel: Optional[Literal["app", "sms", "call_center", "merchant_portal"]] = None
    locale: Optional[Literal["bn", "en", "mixed"]] = None
    message: str = Field(..., min_length=1, description="Free text customer complaint")


# --- Response --------------------------------------------------------------


CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "phishing_or_social_engineering",
    "other",
]
Severity = Literal["low", "medium", "high", "critical"]
Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "fraud_risk",
]


class SortTicketResponse(BaseModel):
    """Outbound structured classification."""

    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)


# --- Health ---------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"