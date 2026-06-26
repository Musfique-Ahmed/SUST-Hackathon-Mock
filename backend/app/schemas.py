"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TicketCreate(BaseModel):
    title: str
    message: str
    category: Optional[str] = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    category: Optional[str] = None
    sentiment: str
    confidence: float
    created_at: datetime
