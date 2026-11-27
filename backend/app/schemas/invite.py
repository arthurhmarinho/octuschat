"""Schemas de convite, cadastro, redefinição de senha e lista de pessoas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.account import AccountRead

# Tipos "crus": a validação com mensagem em português é feita na rota, para o
# `detail` do 422 ser um texto que a tela mostra direto.


class InviteInfo(BaseModel):
    """O que a página pública pode saber de um link. Inválido = tudo vazio."""

    valid: bool = False
    purpose: Literal["signup", "reset"] | None = None
    name: str | None = None
    email: str | None = None
    ig_username: str | None = None


class RegisterIn(BaseModel):
    token: str = Field(max_length=200)
    name: str = Field(max_length=120)
    email: str = Field(max_length=255)
    password: str = Field(max_length=1000)


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=1000)


class OnboardingRead(BaseModel):
    invited_ig_username: str | None
    meta_tester_added: bool
    accounts: list[AccountRead]


# ── Administração ───────────────────────────────────────────


class InviteIn(BaseModel):
    name: str = Field(max_length=120)
    email: str | None = Field(default=None, max_length=255)
    ig_username: str = Field(max_length=100)


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purpose: str
    name: str | None
    email: str | None
    ig_username: str | None
    expires_at: datetime
    meta_tester_added_at: datetime | None
    created_at: datetime


class InviteCreated(BaseModel):
    invite: InviteRead
    # Só aparece nesta resposta: no banco fica o hash.
    token: str


class PersonAccount(BaseModel):
    username: str | None
    needs_reconnect: bool


class PersonRead(BaseModel):
    kind: Literal["user", "invite"]
    status: Literal["pending", "awaiting_instagram", "active", "needs_reconnect"]
    user_id: int | None = None
    is_self: bool = False
    name: str | None
    email: str | None
    # O @ do convite (pode diferir do que a pessoa conectou).
    ig_username: str | None = None
    accounts: list[PersonAccount] = []
    last_login_at: datetime | None = None
    invite_id: int | None = None
    meta_tester_added: bool = False
    # Só no convite pendente.
    expires_at: datetime | None = None


class PeopleRead(BaseModel):
    people: list[PersonRead]
    # Não é segredo (vai na URL do OAuth). None se não tiver cara de ID.
    meta_app_id: str | None


class ResetLinkRead(BaseModel):
    token: str
    expires_at: datetime
