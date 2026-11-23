"""Schemas de saída das execuções de flow (log por automação)."""

from datetime import datetime

from pydantic import BaseModel


class RunContact(BaseModel):
    username: str | None = None
    profile_pic: str | None = None


class FlowRunRead(BaseModel):
    id: int
    contact: RunContact
    status: str
    current_node_id: str | None
    waiting_for: str | None
    resume_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    # Respostas coletadas pelas Perguntas ({"email": "ana@x.com"}).
    vars: dict[str, str]
