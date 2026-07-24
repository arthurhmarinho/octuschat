"""Schemas de entrada/saída para automações."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.automation import KEYWORD_TRIGGERS, TriggerType


class Button(BaseModel):
    label: str
    url: str


class FlowStep(BaseModel):
    """Passo adicional do flow (mensagem enviada após a mensagem 1) — formato
    legado, mantido para retrocompatibilidade; é convertido em cadeia linear."""

    text: str = ""
    buttons: list[Button] | None = None


class FlowNode(BaseModel):
    """Nó do grafo do flow: mensagem ou condição."""

    id: str
    type: Literal["message", "condition"] = "message"
    # message
    text: str = ""
    buttons: list[Button] | None = None
    # condition
    mode: Literal["text_contains", "is_new_contact"] | None = None
    value: str | None = None


class FlowEdge(BaseModel):
    """Aresta do grafo. `branch` só é usado ao sair de um nó de condição."""

    source: str
    target: str
    branch: Literal["yes", "no"] | None = None


class FlowGraph(BaseModel):
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []
    start: str | None = None


MAX_FLOW_NODES = 20


def _validate_buttons(buttons: list[Button] | None) -> None:
    for b in buttons or []:
        if not b.url.startswith(("http://", "https://")):
            raise ValueError("a URL do botão deve começar com http:// ou https://")
        if not b.label.strip():
            raise ValueError("o botão precisa de um rótulo")


def _validate_graph(graph: FlowGraph) -> None:
    """Consistência do grafo: ids, referências e campos por tipo de nó."""
    if not graph.nodes:
        return  # grafo vazio = sem passos extras
    if len(graph.nodes) > MAX_FLOW_NODES:
        raise ValueError(f"o flow pode ter no máximo {MAX_FLOW_NODES} nós")

    ids: set[str] = set()
    for node in graph.nodes:
        if not node.id.strip():
            raise ValueError("todo nó do flow precisa de um id")
        if node.id in ids:
            raise ValueError(f"id de nó duplicado no flow: {node.id}")
        ids.add(node.id)

        if node.type == "message":
            if not node.text.strip() and not node.buttons:
                raise ValueError("nó de mensagem precisa de texto ou botões")
            _validate_buttons(node.buttons)
        elif node.type == "condition":
            if not node.mode:
                raise ValueError("nó de condição precisa de um modo")
            if node.mode == "text_contains" and not (node.value or "").strip():
                raise ValueError("a condição 'texto contém' precisa de um valor")

    for edge in graph.edges:
        if edge.source not in ids:
            raise ValueError(f"aresta com origem inexistente: {edge.source}")
        if edge.target not in ids:
            raise ValueError(f"aresta com destino inexistente: {edge.target}")

    if graph.start and graph.start not in ids:
        raise ValueError(f"o início do flow aponta para um nó inexistente: {graph.start}")


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
    flow: list[FlowStep] | FlowGraph | None = None
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
            _validate_buttons(self.buttons)
        if isinstance(self.flow, FlowGraph):
            _validate_graph(self.flow)
        elif self.flow:
            if len(self.flow) > 5:
                raise ValueError("no máximo 5 mensagens adicionais no flow")
            for step in self.flow:
                if not step.text.strip() and not step.buttons:
                    raise ValueError("cada passo do flow precisa de texto ou botões")
                _validate_buttons(step.buttons)
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
    flow: list[FlowStep] | FlowGraph | None = None
    enabled: bool | None = None


class AutomationRead(AutomationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: str
    created_at: datetime
