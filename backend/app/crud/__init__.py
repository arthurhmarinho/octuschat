"""Camada de acesso a dados. Use como `crud.automation.create(...)`."""

from app.crud import account, automation, contact, message, message_log, webhook_event

__all__ = [
    "account",
    "automation",
    "contact",
    "message",
    "message_log",
    "webhook_event",
]
