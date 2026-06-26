"""Schemas de saída para contas do Instagram (sem expor o token)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ig_user_id: str
    username: str | None
    connected_at: datetime
