"""Validação do grafo único (schemas/automation.py)."""

import pytest
from pydantic import ValidationError

from app.schemas.automation import (
    MAX_FLOW_NODES,
    AutomationCreate,
    AutomationRead,
    AutomationUpdate,
    FlowGraph,
)


def msg(node_id, text="oi", buttons=None):
    n = {"id": node_id, "type": "message", "text": text}
    if buttons is not None:
        n["buttons"] = buttons
    return n


def graph(nodes, edges=(), start="m1"):
    return {"version": 2, "start": start, "nodes": list(nodes), "edges": list(edges)}


def ok(g) -> FlowGraph:
    return FlowGraph.model_validate(g)


def erro(g, trecho: str):
    with pytest.raises(ValidationError) as exc:
        FlowGraph.model_validate(g)
    assert trecho in str(exc.value)


BTN = {"label": "Site", "url": "https://x.com"}


def test_grafo_minimo_valido():
    g = ok(graph([msg("m1")]))
    assert g.start == "m1" and g.version == 2


def test_ids_de_botao_sao_atribuidos():
    g = ok(graph([msg("m1", buttons=[BTN, {**BTN, "label": "Outro"}])]))
    assert [b.id for b in g.nodes[0].buttons] == ["b1", "b2"]
    assert g.nodes[0].buttons[0].type == "web_url"


def test_grafo_completo_com_condicao():
    ok(graph(
        [msg("m1"), {"id": "c", "type": "condition", "mode": "is_new_contact"},
         msg("a"), msg("b")],
        [{"source": "m1", "target": "c"},
         {"source": "c", "target": "a", "branch": "yes"},
         {"source": "c", "target": "b", "branch": "no"}],
    ))


@pytest.mark.parametrize(
    ("g", "trecho"),
    [
        (graph([], start="m1"), "at least 1"),
        (graph([msg("m1")], start="x"), "inexistente"),
        (graph([{"id": "m1", "type": "condition", "mode": "is_new_contact"}]),
         "começar por uma mensagem"),
        (graph([msg("m1", text="  ", buttons=[BTN])]), "mensagem inicial precisa de texto"),
        (graph([msg("m1"), msg("m1")]), "duplicado"),
        (graph([msg("m1"), msg("a", text="")]), "texto ou botões"),
        (graph([msg("m1", buttons=[BTN] * 4)]), "no máximo 3"),
        (graph([msg("m1", buttons=[{"label": "x", "url": "ftp://x"}])]), "http"),
        (graph([msg("m1", buttons=[{"label": " ", "url": "https://x"}])]), "rótulo"),
        (graph([msg("m1", buttons=[{**BTN, "id": "z"}, {**BTN, "id": "z"}])]), "duplicado"),
        (graph([msg("m1")], [{"source": "m1", "target": "x"}]), "destino inexistente"),
        (graph([msg("m1")], [{"source": "x", "target": "m1"}]), "origem inexistente"),
        (graph([msg("m1"), msg("a")], [{"source": "a", "target": "m1"}]), "voltar para a mensagem inicial"),
        (graph([msg("m1"), msg("a"), msg("b")],
               [{"source": "m1", "target": "a"}, {"source": "m1", "target": "b"}]),
         "saída repetida"),
        (graph([msg("m1"), msg("a")], [{"source": "m1", "target": "a", "branch": "yes"}]),
         "porta de saída desconhecida"),
        (graph([msg("m1"), {"id": "c", "type": "condition", "mode": "is_new_contact"}, msg("a")],
               [{"source": "m1", "target": "c"}, {"source": "c", "target": "a"}]),
         "branch 'yes' ou 'no'"),
        (graph([msg("m1"), {"id": "c", "type": "condition"}]), "precisa de um modo"),
        (graph([msg("m1"), {"id": "c", "type": "condition", "mode": "text_contains"}]),
         "precisa de um valor"),
        (graph([msg("m1", text="x" * 1001)]), "1000"),
        (graph([msg("m1")] + [msg(f"n{i}") for i in range(MAX_FLOW_NODES)]), "no máximo"),
    ],
)
def test_grafos_invalidos(g, trecho):
    erro(g, trecho)


def test_automacao_exige_grafo_e_keyword():
    base = {"name": "a", "trigger": "comment_keyword", "account_id": "acc"}
    with pytest.raises(ValidationError, match="graph"):
        AutomationCreate.model_validate({**base, "keyword": "quero"})
    with pytest.raises(ValidationError, match="keyword"):
        AutomationCreate.model_validate({**base, "graph": graph([msg("m1")])})
    a = AutomationCreate.model_validate({**base, "keyword": "quero", "graph": graph([msg("m1")])})
    assert a.graph.nodes[0].text == "oi"


def test_campos_antigos_sao_ignorados():
    a = AutomationCreate.model_validate({
        "name": "a", "trigger": "dm_any", "account_id": "acc",
        "graph": graph([msg("m1")]), "reply_message": "velho", "flow": [{"text": "x"}],
    })
    assert not hasattr(a, "reply_message") and not hasattr(a, "flow")


def test_update_parcial_sem_grafo():
    assert AutomationUpdate.model_validate({"enabled": False}).graph is None


def test_read_aceita_grafo_migrado_que_nao_passaria_no_validador():
    from datetime import datetime, timezone

    g = graph([msg("m1", text=""), msg("s0", text="")], [{"source": "m1", "target": "s0"}])
    r = AutomationRead.model_validate({
        "id": 1, "account_id": "acc", "created_at": datetime.now(timezone.utc),
        "name": "a", "trigger": "dm_any", "graph": g,
    })
    assert r.graph == g
