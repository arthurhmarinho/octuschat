"""Schemas de entrada/saída para automações."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.automation import KEYWORD_TRIGGERS, TriggerType


class Button(BaseModel):
    label: str
    url: str


class FlowStep(BaseModel):
    """Passo adicional do flow (mensagem enviada após a mensagem 1)."""

    text: str = ""
    buttons: list[Button] | None = None


class AutomationBase(BaseModel):
    name: str
    trigger: TriggerType
    keyword: str | None = None
    exclude_keywords: str | None = None
    post_id: str | None = None
    bind_next: bool = False
    reply_message: str
    public_reply: str | None = None
    link_url: str | None = None
    link_label: str | None = None
    buttons: list[Button] | None = None
    flow: list[FlowStep] | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def _validate(self):
        if self.trigger in KEYWORD_TRIGGERS and not self.keyword:
            raise ValueError("keyword é obrigatória para gatilhos de palavra-chave")
        if self.link_url and not self.link_url.startswith(("http://", "https://")):
            raise ValueError("link_url deve começar com http:// ou https://")
        if self.link_label and not self.link_url:
            raise ValueError("link_url é obrigatório quando há link_label")
        if self.buttons:
            if len(self.buttons) > 3:
                raise ValueError("no máximo 3 botões")
            for b in self.buttons:
                if not b.url.startswith(("http://", "https://")):
                    raise ValueError("a URL do botão deve começar com http:// ou https://")
                if not b.label.strip():
                    raise ValueError("o botão precisa de um rótulo")
        if self.flow:
            if len(self.flow) > 5:
                raise ValueError("no máximo 5 mensagens adicionais no flow")
            for step in self.flow:
                if not step.text.strip() and not step.buttons:
                    raise ValueError("cada passo do flow precisa de texto ou botões")
                for b in step.buttons or []:
                    if not b.url.startswith(("http://", "https://")):
                        raise ValueError("a URL do botão deve começar com http:// ou https://")
                    if not b.label.strip():
                        raise ValueError("o botão precisa de um rótulo")
        return self


class AutomationCreate(AutomationBase):
    account_id: str


class AutomationUpdate(BaseModel):
    name: str | None = None
    trigger: TriggerType | None = None
    keyword: str | None = None
    exclude_keywords: str | None = None
    post_id: str | None = None
    bind_next: bool | None = None
    reply_message: str | None = None
    public_reply: str | None = None
    link_url: str | None = None
    link_label: str | None = None
    buttons: list[Button] | None = None
    flow: list[FlowStep] | None = None
    enabled: bool | None = None


class AutomationRead(AutomationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: str
    created_at: datetime
