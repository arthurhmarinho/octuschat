"""Schemas de usuário e login."""

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    is_admin: bool
    must_change_password: bool


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1000)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=1000)
    new_password: str = Field(max_length=1000)
