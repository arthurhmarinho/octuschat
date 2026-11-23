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


# ═══════════════════════════ Grafo v3 ═══════════════════════════


def g3(nodes, edges=(), start="n1"):
    return {"version": 3, "start": start, "nodes": list(nodes), "edges": list(edges)}


def mq(node_id="n1", text="Quer?", n=2, **kw):
    """Mensagem com `n` respostas rápidas (q1…qn)."""
    return {"id": node_id, "type": "message", "text": text,
            "quick_replies": [{"id": f"q{i}", "title": f"Op {i}"} for i in range(1, n + 1)], **kw}


QUESTION = {"id": "p", "type": "question", "text": "Qual seu e-mail?", "save_as": "email"}
IMAGE = {"id": "i", "type": "image", "url": "https://x.com/foto.jpg"}
DELAY = {"id": "d", "type": "delay", "hours": 2}
COND_VAR = {"id": "c", "type": "condition", "mode": "var_contains", "var": "email", "value": "@"}


def test_v3_um_caso_valido_por_tipo_de_no():
    ok(g3([msg("n1", "Oi {{username}}")]))                                   # mensagem
    ok(g3([msg("n1", buttons=[BTN])]))                                       # mensagem + links
    ok(g3([mq()]))                                                           # mensagem + respostas
    ok(g3([QUESTION], start="p"))                                            # pergunta como início
    ok(g3([IMAGE], start="i"))                                               # imagem como início
    ok(g3([msg("n1"), DELAY], [{"source": "n1", "target": "d"}]))            # espera
    ok(g3([msg("n1"), QUESTION, COND_VAR, msg("a"), msg("b")], [
        {"source": "n1", "target": "p"},
        {"source": "p", "target": "c", "branch": "answered"},
        {"source": "c", "target": "a", "branch": "yes"},
        {"source": "c", "target": "b", "branch": "no"},
    ]))


def test_v3_fluxo_com_respostas_rapidas_e_todas_as_saidas():
    g = ok(g3(
        [mq(), QUESTION, DELAY, msg("fim")],
        [
            {"source": "n1", "target": "p", "branch": "qr:q1"},
            {"source": "n1", "target": "d", "branch": "qr:q2"},
            {"source": "n1", "target": "fim", "branch": "other"},
            {"source": "p", "target": "fim", "branch": "timeout"},
            {"source": "d", "target": "fim"},
        ],
    ))
    assert g.version == 3 and len(g.nodes) == 4


def test_v3_ids_de_resposta_rapida_sao_atribuidos():
    n = {"id": "n1", "type": "message", "text": "Oi",
         "quick_replies": [{"title": "A"}, {"title": "B"}]}
    g = ok(g3([n]))
    assert [q.id for q in g.nodes[0].quick_replies] == ["q1", "q2"]


def test_v3_versao_padrao_e_3_e_so_aceita_2_ou_3():
    assert ok({"start": "m1", "nodes": [msg("m1")]}).version == 3
    erro({"version": 4, "start": "m1", "nodes": [msg("m1")]}, "version")


def test_v2_antigo_continua_valido_inclusive_sem_type_no_no():
    ok(graph([{"id": "m1", "text": "sem type"}]))
    ok(graph([msg("m1"), {"id": "c", "type": "condition", "mode": "text_contains", "value": "x"},
              msg("a"), msg("b")],
         [{"source": "m1", "target": "c"},
          {"source": "c", "target": "a", "branch": "yes"},
          {"source": "c", "target": "b", "branch": "no"}]))


def test_v3_texto_conta_bytes_e_nao_caracteres():
    # 300 emojis = 300 caracteres, 1200 bytes
    erro(g3([msg("n1", "😀" * 300)]), "1000 bytes")
    ok(g3([msg("n1", "😀" * 250)]))               # 1000 bytes certinhos
    erro(g3([msg("n1", "😀" * 251)]), "1000 bytes")
    erro(g3([msg("n1", "é" * 501)]), "1000 bytes")  # 'é' = 2 bytes


def test_v3_com_botoes_o_limite_e_640_bytes():
    ok(g3([msg("n1", "x" * 640, buttons=[BTN])]))
    erro(g3([msg("n1", "x" * 641, buttons=[BTN])]), "640 bytes")
    ok(g3([msg("n1", "x" * 1000)]))                 # sem botões, 1000 pode


@pytest.mark.parametrize(
    ("g", "trecho"),
    [
        # mensagem
        (g3([msg("n1", buttons=[BTN]) | {"quick_replies": [{"title": "A"}]}]),
         "não podem ficar na mesma mensagem"),
        (g3([mq(n=14)]), "no máximo 13"),
        (g3([{"id": "n1", "type": "message", "text": "Oi",
              "quick_replies": [{"title": "x" * 21}]}]), "passa de 20"),
        (g3([{"id": "n1", "type": "message", "text": "Oi",
              "quick_replies": [{"title": "  "}]}]), "precisa de um título"),
        (g3([{"id": "n1", "type": "message", "text": "Oi",
              "quick_replies": [{"id": "z", "title": "A"}, {"id": "z", "title": "B"}]}]), "duplicado"),
        (g3([msg("n1") | {"timeout_hours": 2}]), "só vale em mensagem com respostas rápidas"),
        (g3([mq(timeout_hours=0.05)]), "entre 0.1 e 23"),
        (g3([mq(timeout_hours=24)]), "entre 0.1 e 23"),
        # pergunta
        (g3([{**QUESTION, "text": " "}], start="p"), "precisa de texto"),
        (g3([{**QUESTION, "save_as": ""}], start="p"), "nome da variável"),
        (g3([{**QUESTION, "save_as": "Email"}], start="p"), "nome da variável"),
        (g3([{**QUESTION, "save_as": "1abc"}], start="p"), "nome da variável"),
        (g3([{**QUESTION, "save_as": "a" * 31}], start="p"), "nome da variável"),
        (g3([{**QUESTION, "timeout_hours": 30}], start="p"), "entre 0.1 e 23"),
        # condição
        (g3([msg("n1"), {"id": "c", "type": "condition", "mode": "var_contains", "var": "email"}]),
         "precisa de um valor"),
        (g3([msg("n1"), {"id": "c", "type": "condition", "mode": "var_exists", "var": "Bad Var"}]),
         "variável válida"),
        (g3([msg("n1"), {"id": "c", "type": "condition", "mode": "var_exists"}]), "variável válida"),
        (g3([msg("n1"), {"id": "c", "type": "condition", "mode": "outro"}]), "mode"),
        # imagem
        (g3([IMAGE | {"url": "ftp://x/a.png"}], start="i"), "http"),
        (g3([IMAGE | {"url": ""}], start="i"), "http"),
        # espera
        (g3([msg("n1"), DELAY | {"hours": 0.01}]), "entre 0.1 e 23"),
        (g3([msg("n1"), DELAY | {"hours": 23.5}]), "entre 0.1 e 23"),
        # início
        (g3([DELAY], start="d"), "começar por uma mensagem, pergunta ou imagem"),
        (g3([COND_VAR], start="c"), "começar por uma mensagem, pergunta ou imagem"),
        # nós
        (g3([msg("n1")] + [msg(f"n{i}") for i in range(2, 52)]), "no máximo 50"),
    ],
)
def test_v3_regras_quebradas(g, trecho):
    erro(g, trecho)


def test_v3_limite_de_50_nos_aceita_50():
    ok(g3([msg("n1")] + [msg(f"n{i}") for i in range(2, 51)]))


@pytest.mark.parametrize(
    ("g", "trecho"),
    [
        # saídas por tipo de nó
        (g3([msg("n1"), msg("a")], [{"source": "n1", "target": "a", "branch": "qr:q1"}]),
         "porta de saída desconhecida"),
        (g3([mq(), msg("a")], [{"source": "n1", "target": "a"}]), "porta de saída desconhecida"),
        (g3([mq(), msg("a")], [{"source": "n1", "target": "a", "branch": "qr:q9"}]),
         "porta de saída desconhecida"),
        (g3([mq(), msg("a")], [{"source": "n1", "target": "a", "branch": "answered"}]),
         "porta de saída desconhecida"),
        (g3([QUESTION, msg("a")], [{"source": "p", "target": "a"}], start="p"),
         "porta de saída desconhecida"),
        (g3([QUESTION, msg("a")], [{"source": "p", "target": "a", "branch": "yes"}], start="p"),
         "porta de saída desconhecida"),
        (g3([msg("n1"), DELAY, msg("a")], [{"source": "n1", "target": "d"},
                                           {"source": "d", "target": "a", "branch": "yes"}]),
         "porta de saída desconhecida"),
        (g3([msg("n1"), IMAGE, msg("a")], [{"source": "n1", "target": "i"},
                                           {"source": "i", "target": "a", "branch": "other"}]),
         "porta de saída desconhecida"),
        # saída usada duas vezes
        (g3([mq(), msg("a"), msg("b")], [{"source": "n1", "target": "a", "branch": "qr:q1"},
                                         {"source": "n1", "target": "b", "branch": "qr:q1"}]),
         "saída repetida"),
        # ciclos
        (g3([msg("n1"), msg("a"), msg("b")], [{"source": "n1", "target": "a"},
                                              {"source": "a", "target": "b"},
                                              {"source": "b", "target": "a"}]), "ciclos"),
        (g3([msg("n1"), msg("a")], [{"source": "n1", "target": "a"}, {"source": "a", "target": "a"}]),
         "ele mesmo"),
        (g3([msg("n1"), msg("a")], [{"source": "n1", "target": "a"}, {"source": "a", "target": "n1"}]),
         "voltar para a mensagem inicial"),
    ],
)
def test_v3_saidas_e_ciclos(g, trecho):
    erro(g, trecho)


def test_v3_no_inalcancavel_e_so_aviso_nao_bloqueia():
    ok(g3([msg("n1"), msg("solto")]))


def test_v3_ciclo_fora_do_caminho_tambem_e_recusado():
    erro(g3([msg("n1"), msg("a"), msg("b")], [{"source": "a", "target": "b"},
                                              {"source": "b", "target": "a"}]), "ciclos")


def test_v3_posicao_e_guardada_em_qualquer_tipo_de_no():
    g = ok(g3([msg("n1") | {"position": {"x": 1, "y": 2}}, DELAY | {"position": {"x": 3.5, "y": 4}}],
              [{"source": "n1", "target": "d"}]))
    assert g.nodes[1].position.x == 3.5


# ── gatilho x início ──


def auto(trigger, graph_, **kw):
    return AutomationCreate.model_validate(
        {"name": "a", "trigger": trigger, "account_id": "acc", "graph": graph_, **kw})


def test_gatilho_de_comentario_exige_mensagem_no_inicio():
    auto("comment_any", g3([msg("n1")]))
    with pytest.raises(ValidationError, match="primeiro nó precisa ser uma mensagem"):
        auto("comment_any", g3([QUESTION], start="p"))
    with pytest.raises(ValidationError, match="primeiro nó precisa ser uma mensagem"):
        auto("comment_keyword", g3([IMAGE], start="i"), keyword="oi")


@pytest.mark.parametrize("trigger", ["dm_any", "story_reply", "story_mention"])
def test_outros_gatilhos_aceitam_pergunta_ou_imagem_no_inicio(trigger):
    auto(trigger, g3([QUESTION], start="p"))
    auto(trigger, g3([IMAGE], start="i"))
    auto(trigger, g3([msg("n1")]))


def test_dm_keyword_aceita_pergunta_no_inicio():
    auto("dm_keyword", g3([QUESTION], start="p"), keyword="oi")
