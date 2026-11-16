"""Schemas de entrada/saída para automações.

O conteúdo da automação é UM grafo (`graph`):

    {"version": 2, "start": "m1",
     "nodes": [{"id": "m1", "type": "message", "text": "Oi!",
                "buttons": [{"id": "b1", "type": "web_url", "label": "Site",
                             "url": "https://..."}]},
               {"id": "c1", "type": "condition", "mode": "is_new_contact"},
               {"id": "m2", "type": "message", "text": "Bem-vindo"}],
     "edges": [{"source": "m1", "target": "c1"},
               {"source": "c1", "target": "m2", "branch": "yes"}]}

- `start` é a mensagem 1 (sempre um nó de mensagem): no gatilho de
  comentário ela vai como private reply.
- `branch` é a porta de saída da aresta: ausente = saída padrão;
  "yes"/"no" = ramos de uma condição.
- Novos tipos de nó (delay, ação, IA…) entram como novos `type`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.automation import KEYWORD_TRIGGERS, TriggerType

GRAPH_VERSION = 2
MAX_FLOW_NODES = 20
MAX_BUTTONS = 3
MAX_TEXT = 1000  # limite da Meta para texto; o button template corta em 640


class Button(BaseModel):
    id: str | None = None  # atribuído na validação se faltar (b1, b2…)
    type: Literal["web_url"] = "web_url"
    label: str
    url: str


class Position(BaseModel):
    x: float
    y: float


class FlowNode(BaseModel):
    """Nó do grafo: mensagem ou condição."""

    id: str
    type: Literal["message", "condition"] = "message"
    # message
    text: str = ""
    buttons: list[Button] | None = None
    # condition
    mode: Literal["text_contains", "is_new_contact"] | None = None
    value: str | None = None
    # posição no canvas (opcional; o canvas atual faz o layout sozinho)
    position: Position | None = None


class FlowEdge(BaseModel):
    """Aresta. `branch` = porta de saída (ausente = saída padrão)."""

    source: str
    target: str
    branch: str | None = None


class FlowGraph(BaseModel):
    version: Literal[2] = GRAPH_VERSION
    start: str
    nodes: list[FlowNode] = Field(min_length=1)
    edges: list[FlowEdge] = []

    @model_validator(mode="after")
    def _validate(self):
        validate_graph(self)
        return self


CONDITION_BRANCHES = {"yes", "no"}


def _validate_buttons(node: FlowNode) -> None:
    buttons = node.buttons or []
    if len(buttons) > MAX_BUTTONS:
        raise ValueError(f"no máximo {MAX_BUTTONS} botões por mensagem")
    seen: set[str] = set()
    for i, b in enumerate(buttons):
        if not b.url.startswith(("http://", "https://")):
            raise ValueError("a URL do botão deve começar com http:// ou https://")
        if not b.label.strip():
            raise ValueError("o botão precisa de um rótulo")
        if not b.id:
            b.id = f"b{i + 1}"
            while b.id in seen:
                b.id += "_"
        if b.id in seen:
            raise ValueError(f"id de botão duplicado na mensagem {node.id}: {b.id}")
        seen.add(b.id)


def validate_graph(graph: FlowGraph) -> None:
    """Consistência: ids, referências, início e campos por tipo de nó."""
    if len(graph.nodes) > MAX_FLOW_NODES:
        raise ValueError(f"o flow pode ter no máximo {MAX_FLOW_NODES} nós")

    by_id: dict[str, FlowNode] = {}
    for node in graph.nodes:
        if not node.id.strip():
            raise ValueError("todo nó do flow precisa de um id")
        if node.id in by_id:
            raise ValueError(f"id de nó duplicado no flow: {node.id}")
        by_id[node.id] = node

        if node.type == "message":
            if not node.text.strip() and not node.buttons:
                raise ValueError("nó de mensagem precisa de texto ou botões")
            if len(node.text) > MAX_TEXT:
                raise ValueError(f"mensagem com mais de {MAX_TEXT} caracteres")
            _validate_buttons(node)
        elif node.type == "condition":
            if not node.mode:
                raise ValueError("nó de condição precisa de um modo")
            if node.mode == "text_contains" and not (node.value or "").strip():
                raise ValueError("a condição 'texto contém' precisa de um valor")

    start = by_id.get(graph.start)
    if start is None:
        raise ValueError(f"o início do flow aponta para um nó inexistente: {graph.start}")
    if start.type != "message":
        raise ValueError("o flow precisa começar por uma mensagem")
    if not start.text.strip():
        raise ValueError("a mensagem inicial precisa de texto")

    ports: set[tuple[str, str | None]] = set()
    for edge in graph.edges:
        source = by_id.get(edge.source)
        if source is None:
            raise ValueError(f"aresta com origem inexistente: {edge.source}")
        if edge.target not in by_id:
            raise ValueError(f"aresta com destino inexistente: {edge.target}")
        if edge.target == graph.start:
            raise ValueError("nenhuma aresta pode voltar para a mensagem inicial")
        if source.type == "condition":
            if edge.branch not in CONDITION_BRANCHES:
                raise ValueError("arestas de condição precisam de branch 'yes' ou 'no'")
        elif edge.branch is not None:
            raise ValueError(f"porta de saída desconhecida em {edge.source}: {edge.branch}")
        port = (edge.source, edge.branch)
        if port in ports:
            raise ValueError(f"saída repetida em {edge.source}")
        ports.add(port)


class AutomationBase(BaseModel):
    name: str
    trigger: TriggerType
    keyword: str | None = None
    exclude_keywords: str | None = None
    post_id: str | None = None
    bind_next: bool = False
    public_reply: str | None = None
    graph: FlowGraph
    enabled: bool = True

    @model_validator(mode="after")
    def _validate(self):
        if self.trigger in KEYWORD_TRIGGERS and not self.keyword:
            raise ValueError("keyword é obrigatória para gatilhos de palavra-chave")
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
    public_reply: str | None = None
    graph: FlowGraph | None = None
    enabled: bool | None = None


class AutomationRead(AutomationBase):
    model_config = ConfigDict(from_attributes=True)

    # Na leitura o grafo vem como está no banco (dados migrados podem não
    # passar no validador estrito — ex.: passo vazio — e a tela precisa abri-los).
    graph: dict
    id: int
    account_id: str
    created_at: datetime
