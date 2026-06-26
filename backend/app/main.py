"""FastAPI entrypoint for the Ticket Analyzer backend."""
from typing import List

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Importing the sentiment module here loads the HF model into memory
# before the first request is served (PDR §9).
from . import sentiment  # noqa: F401  (side-effect: model load)
from .database import Base, engine, get_db
from .models import Ticket
from .schemas import TicketCreate, TicketOut

# Auto-create the tickets table for a fresh Postgres volume (PDR §12).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ticket Analyzer", version="1.0.0")

# CORS is enabled as a fallback. In production the frontend Nginx
# container reverse-proxies /api to this service, so CORS is bypassed
# entirely (PDR §12).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    label, confidence = sentiment.analyze(payload.message)
    ticket = Ticket(
        title=payload.title,
        message=payload.message,
        category=payload.category,
        sentiment=label,
        confidence=confidence,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.get("/tickets", response_model=List[TicketOut])
def list_tickets(db: Session = Depends(get_db)):
    return (
        db.query(Ticket)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .all()
    )
