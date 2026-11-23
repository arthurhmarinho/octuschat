"""Schemas de entrada/saída para automações.

O conteúdo da automação é UM grafo (`graph`). Versão 3 (a que o editor grava):

    {"version": 3, "start": "n1",
     "nodes": [
       {"id": "n1", "type": "message", "text": "Oi {{username}}, quer o link?",
        "quick_replies": [{"id": "q1", "title": "Quero"}, {"id": "q2", "title": "Agora não"}],
        "timeout_hours": 23},
       {"id": "n2", "type": "question", "text": "Qual seu e-mail?", "save_as": "email"},
       {"id": "n3", "type": "condition", "mode": "var_contains", "var": "email", "value": "@"},
       {"id": "n4", "type": "image", "url": "https://.../foto.jpg"},
       {"id": "n5", "type": "delay", "hours": 2}],
     "edges": [{"source": "n1", "target": "n2", "branch": "qr:q1"},
               {"source": "n1", "target": "n5", "branch": "qr:q2"}]}

Retrocompatível: grafos v2 (só `message`/`condition`, `branch` null/yes/no)
continuam válidos.

- `start` é o primeiro nó depois do gatilho e não recebe arestas. No gatilho de
  comentário ele é uma mensagem (vai como private reply); nos outros pode ser
  mensagem, pergunta ou imagem.
- `branch` é a saída da aresta (ver `outputs_of`). Uma saída sem aresta é o FIM
  daquele caminho, e isso é válido.
- Sem ciclos. No máximo 50 nós.
"""

import re
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.automation import COMMENT_TRIGGERS, KEYWORD_TRIGGERS, TriggerType

GRAPH_VERSION = 3
MAX_FLOW_NODES = 50
MAX_BUTTONS = 3
MAX_QUICK_REPLIES = 13
QUICK_REPLY_TITLE_MAX = 20  # caracteres (limite da Meta)
# Limites da Meta, em BYTES UTF-8 (não em caracteres): o emoji pesa 4.
MAX_TEXT = 1000
MAX_TEXT_WITH_BUTTONS = 640  # o button template corta em 640
MIN_HOURS = 0.1
MAX_HOURS = 23  # a janela de 24h da Meta fecha: nenhum prazo passa de 23 h
VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
CONDITION_MODES = ("text_contains", "is_new_contact", "var_contains", "var_exists")


def text_bytes(text: str) -> int:
    """Tamanho como a Meta conta: bytes UTF-8."""
    return len(text.encode("utf-8"))


class Button(BaseModel):
    id: str | None = None  # atribuído na validação se faltar (b1, b2…)
    type: Literal["web_url"] = "web_url"
    label: str
    url: str


class QuickReply(BaseModel):
    id: str | None = None  # atribuído na validação se faltar (q1, q2…)
    title: str


class Position(BaseModel):
    x: float
    y: float


class _Node(BaseModel):
    id: str
    # posição no canvas (opcional: sem ela o editor faz o layout)
    position: Position | None = None


def _check_hours(value: float | None, label: str) -> None:
    if value is not None and not (MIN_HOURS <= value <= MAX_HOURS):
        raise ValueError(f"{label} precisa ficar entre {MIN_HOURS} e {MAX_HOURS} horas")


class MessageNode(_Node):
    type: Literal["message"] = "message"
    text: str = ""
    buttons: list[Button] | None = None
    quick_replies: list[QuickReply] | None = None
    # Só com respostas rápidas: quanto esperar pelo toque (padrão 23 h).
    timeout_hours: float | None = None

    @model_validator(mode="after")
    def _validate(self):
        buttons = self.buttons or []
        replies = self.quick_replies or []
        if not self.text.strip() and not buttons and not replies:
            raise ValueError("nó de mensagem precisa de texto ou botões (ou respostas rápidas)")
        if buttons and replies:
            raise ValueError("botões de link e respostas rápidas não podem ficar na mesma mensagem")
        if replies and not self.text.strip():
            raise ValueError("a mensagem com respostas rápidas precisa de texto")
        limit = MAX_TEXT_WITH_BUTTONS if buttons else MAX_TEXT
        if text_bytes(self.text) > limit:
            raise ValueError(f"mensagem com mais de {limit} bytes")

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
                raise ValueError(f"id de botão duplicado na mensagem {self.id}: {b.id}")
            seen.add(b.id)

        if len(replies) > MAX_QUICK_REPLIES:
            raise ValueError(f"no máximo {MAX_QUICK_REPLIES} respostas rápidas por mensagem")
        seen = set()
        for i, q in enumerate(replies):
            if not q.title.strip():
                raise ValueError("a resposta rápida precisa de um título")
            if len(q.title) > QUICK_REPLY_TITLE_MAX:
                raise ValueError(
                    f"o título da resposta rápida passa de {QUICK_REPLY_TITLE_MAX} caracteres"
                )
            if not q.id:
                q.id = f"q{i + 1}"
                while q.id in seen:
                    q.id += "_"
            if q.id in seen:
                raise ValueError(f"id de resposta rápida duplicado na mensagem {self.id}: {q.id}")
            seen.add(q.id)

        if self.timeout_hours is not None and not replies:
            raise ValueError("timeout_hours só vale em mensagem com respostas rápidas")
        _check_hours(self.timeout_hours, "o tempo de espera")
        return self


class QuestionNode(_Node):
    type: Literal["question"] = "question"
    text: str = ""
    save_as: str = ""
    timeout_hours: float | None = None

    @model_validator(mode="after")
    def _validate(self):
        if not self.text.strip():
            raise ValueError("nó de pergunta precisa de texto")
        if text_bytes(self.text) > MAX_TEXT:
            raise ValueError(f"pergunta com mais de {MAX_TEXT} bytes")
        if not VAR_RE.match(self.save_as):
            raise ValueError(
                "o nome da variável precisa começar com letra minúscula e ter só "
                "letras minúsculas, números e _ (até 30 caracteres)"
            )
        _check_hours(self.timeout_hours, "o tempo de espera")
        return self


class ConditionNode(_Node):
    type: Literal["condition"] = "condition"
    mode: Literal["text_contains", "is_new_contact", "var_contains", "var_exists"] | None = None
    value: str | None = None
    var: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        if not self.mode:
            raise ValueError("nó de condição precisa de um modo")
        if self.mode in ("text_contains", "var_contains") and not (self.value or "").strip():
            raise ValueError(f"a condição '{self.mode}' precisa de um valor")
        if self.mode in ("var_contains", "var_exists") and not VAR_RE.match(self.var or ""):
            raise ValueError(f"a condição '{self.mode}' precisa de uma variável válida")
        return self


class ImageNode(_Node):
    type: Literal["image"] = "image"
    url: str = ""

    @model_validator(mode="after")
    def _validate(self):
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("a URL da imagem deve começar com http:// ou https://")
        return self


class DelayNode(_Node):
    type: Literal["delay"] = "delay"
    hours: float

    @model_validator(mode="after")
    def _validate(self):
        _check_hours(self.hours, "a espera")
        return self


FlowNode = Annotated[
    Union[MessageNode, QuestionNode, ConditionNode, ImageNode, DelayNode],
    Field(discriminator="type"),
]


class FlowEdge(BaseModel):
    """Aresta. `branch` = saída do nó de origem (ausente = saída padrão)."""

    source: str
    target: str
    branch: str | None = None


def outputs_of(node) -> list[str | None]:
    """Saídas válidas (`branch`) de um nó. `None` = a saída padrão, sem nome."""
    if isinstance(node, MessageNode):
        if node.quick_replies:
            return [f"qr:{q.id}" for q in node.quick_replies] + ["other", "timeout"]
        return [None]
    if isinstance(node, QuestionNode):
        return ["answered", "timeout"]
    if isinstance(node, ConditionNode):
        return ["yes", "no"]
    return [None]  # image, delay


class FlowGraph(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: Literal[2, 3] = GRAPH_VERSION
    start: str
    nodes: list[FlowNode] = Field(min_length=1)
    edges: list[FlowEdge] = []

    @model_validator(mode="before")
    @classmethod
    def _default_node_type(cls, data):
        # Grafos antigos podem omitir `type` (era "message" por padrão).
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            data = {
                **data,
                "nodes": [
                    {"type": "message", **n} if isinstance(n, dict) and "type" not in n else n
                    for n in data["nodes"]
                ],
            }
        return data

    @model_validator(mode="after")
    def _validate(self):
        validate_graph(self)
        return self


def _find_cycle(by_id: dict, edges: list[FlowEdge]) -> bool:
    """True se houver ciclo (Kahn: sobra nó com grau de entrada > 0)."""
    indeg = {nid: 0 for nid in by_id}
    out: dict[str, list[str]] = {nid: [] for nid in by_id}
    for e in edges:
        out[e.source].append(e.target)
        indeg[e.target] += 1
    queue = [n for n, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return seen != len(by_id)


def validate_graph(graph: FlowGraph) -> None:
    """Consistência: ids, referências, início, saídas por tipo e ciclos."""
    if len(graph.nodes) > MAX_FLOW_NODES:
        raise ValueError(f"o flow pode ter no máximo {MAX_FLOW_NODES} nós")

    by_id: dict = {}
    for node in graph.nodes:
        if not node.id.strip():
            raise ValueError("todo nó do flow precisa de um id")
        if node.id in by_id:
            raise ValueError(f"id de nó duplicado no flow: {node.id}")
        by_id[node.id] = node

    start = by_id.get(graph.start)
    if start is None:
        raise ValueError(f"o início do flow aponta para um nó inexistente: {graph.start}")
    if not isinstance(start, (MessageNode, QuestionNode, ImageNode)):
        raise ValueError("o flow precisa começar por uma mensagem, pergunta ou imagem")
    if isinstance(start, MessageNode) and not start.text.strip():
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
        if edge.target == edge.source:
            raise ValueError(f"o nó {edge.source} não pode se ligar a ele mesmo")
        valid = outputs_of(source)
        if edge.branch not in valid:
            if isinstance(source, ConditionNode):
                raise ValueError("arestas de condição precisam de branch 'yes' ou 'no'")
            raise ValueError(f"porta de saída desconhecida em {edge.source}: {edge.branch}")
        port = (edge.source, edge.branch)
        if port in ports:
            raise ValueError(f"saída repetida em {edge.source}")
        ports.add(port)

    if _find_cycle(by_id, graph.edges):
        raise ValueError("o flow não pode ter ciclos")


def check_start_for_trigger(start_type: str | None, trigger: TriggerType) -> None:
    """No gatilho de comentário o 1º nó é a private reply, então tem de ser mensagem."""
    if trigger in COMMENT_TRIGGERS and start_type != "message":
        raise ValueError("no gatilho de comentário o primeiro nó precisa ser uma mensagem")


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
        # Na leitura (`AutomationRead`) o grafo é o dict cru do banco: não revalida.
        if isinstance(self.graph, FlowGraph):
            start = next((n for n in self.graph.nodes if n.id == self.graph.start), None)
            check_start_for_trigger(start.type if start else None, self.trigger)
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
