"""Schemas de saída para contas do Instagram (sem expor o token)."""

from datetime import datetime

from datetime import timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ig_user_id: str
    username: str | None
    connected_at: datetime
    token_expires_at: datetime | None = None
    # Não vai na resposta: só alimenta `needs_reconnect`.
    token_invalid_at: datetime | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def needs_reconnect(self) -> bool:
        """A Meta recusou o token (190) ou ele já passou da validade."""
        if self.token_invalid_at is not None:
            return True
        exp = self.token_expires_at
        if exp is None:
            return False
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp <= datetime.now(timezone.utc)
