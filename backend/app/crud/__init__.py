"""Camada de acesso a dados. Use como `crud.automation.create(...)`."""

from app.crud import account, automation, contact, message, message_log, user, webhook_event

__all__ = [
    "account",
    "automation",
    "contact",
    "message",
    "message_log",
    "user",
    "webhook_event",
]
