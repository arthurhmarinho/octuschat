"""Testes do cliente da Graph API — sem rede (httpx.MockTransport)."""

import httpx
import pytest

from app.services import instagram_api
from app.services.instagram_api import InstagramAPIError

TOKEN = "IGAAsegredo-do-teste-1234567890abcdef"


@pytest.fixture
def mock_meta(monkeypatch):
    """Troca o transporte HTTP. Devolve (lista de requests, setter da resposta)."""
    calls: list[httpx.Request] = []
    state = {"responses": [httpx.Response(200, json={"ok": True})]}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        resps = state["responses"]
        return resps.pop(0) if len(resps) > 1 else resps[0]

    monkeypatch.setattr(
        instagram_api,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    async def no_sleep(_):
        return None

    monkeypatch.setattr(instagram_api.asyncio, "sleep", no_sleep)

    def respond(*responses: httpx.Response):
        state["responses"] = list(responses)

    return calls, respond


def _assert_token_no_header_e_fora_da_url(req: httpx.Request):
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(req.url)
    assert "access_token" not in str(req.url)


async def test_send_message_usa_header_e_nao_url(mock_meta):
    calls, _ = mock_meta
    await instagram_api.send_message_to_user("123", "456", "oi", TOKEN)
    req = calls[0]
    assert req.method == "POST"
    assert req.url.path.endswith("/123/messages")
    _assert_token_no_header_e_fora_da_url(req)


@pytest.mark.parametrize(
    "chamada",
    [
        lambda: instagram_api.reply_privately_to_comment("1", "c1", "oi", TOKEN),
        lambda: instagram_api.reply_publicly_to_comment("c1", "valeu!", TOKEN),
        lambda: instagram_api.get_profile("1", TOKEN),
        lambda: instagram_api.get_user_profile("igsid", TOKEN),
        lambda: instagram_api.subscribe_webhooks("1", TOKEN),
        lambda: instagram_api.get_subscribed_apps("1", TOKEN),
        lambda: instagram_api.list_media("1", TOKEN),
    ],
)
async def test_todas_as_chamadas_autenticadas_usam_header(mock_meta, chamada):
    calls, _ = mock_meta
    await chamada()
    _assert_token_no_header_e_fora_da_url(calls[0])


async def test_parametros_continuam_na_query(mock_meta):
    calls, _ = mock_meta
    await instagram_api.reply_publicly_to_comment("c1", "Enviei no direct", TOKEN)
    assert calls[0].url.params["message"] == "Enviei no direct"


async def test_list_media_devolve_data(mock_meta):
    _, respond = mock_meta
    respond(httpx.Response(200, json={"data": [{"id": "m1"}]}))
    assert await instagram_api.list_media("1", TOKEN) == [{"id": "m1"}]


async def test_endpoints_de_token_usam_parametro(mock_meta):
    calls, _ = mock_meta
    await instagram_api.refresh_long_lived(TOKEN)
    assert calls[0].url.params["access_token"] == TOKEN
    assert "Authorization" not in calls[0].headers


async def test_erro_da_meta_vira_excecao_sem_token(mock_meta):
    _, respond = mock_meta
    respond(
        httpx.Response(
            400,
            json={"error": {"message": "Invalid OAuth access token", "code": 190}},
        )
    )
    with pytest.raises(InstagramAPIError) as exc:
        await instagram_api.refresh_long_lived(TOKEN)  # token vai na URL aqui
    msg = str(exc.value)
    assert exc.value.status_code == 400
    assert "Invalid OAuth access token (code 190)" in msg
    assert TOKEN not in msg
    assert "graph.instagram.com" not in msg


async def test_4xx_nao_repete(mock_meta):
    calls, respond = mock_meta
    respond(httpx.Response(400, json={"error": {"message": "bad"}}))
    with pytest.raises(InstagramAPIError):
        await instagram_api.send_message_to_user("1", "2", "oi", TOKEN)
    assert len(calls) == 1


async def test_5xx_repete_e_depois_funciona(mock_meta):
    calls, respond = mock_meta
    respond(httpx.Response(500), httpx.Response(503), httpx.Response(200, json={"id": "x"}))
    assert await instagram_api.send_message_to_user("1", "2", "oi", TOKEN) == {"id": "x"}
    assert len(calls) == 3


async def test_5xx_persistente_desiste_apos_retries(mock_meta):
    calls, respond = mock_meta
    respond(httpx.Response(500))
    with pytest.raises(InstagramAPIError):
        await instagram_api.send_message_to_user("1", "2", "oi", TOKEN)
    assert len(calls) == 3  # 1 + 2 retries


async def test_get_nao_repete_em_5xx(mock_meta):
    calls, respond = mock_meta
    respond(httpx.Response(500))
    with pytest.raises(InstagramAPIError):
        await instagram_api.get_profile("1", TOKEN)
    assert len(calls) == 1


async def test_erro_de_rede_vira_excecao_sem_token(monkeypatch):
    def handler(request):
        raise httpx.ConnectError(f"falhou {request.url}", request=request)

    monkeypatch.setattr(
        instagram_api,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(InstagramAPIError) as exc:
        await instagram_api.refresh_long_lived(TOKEN)
    assert TOKEN not in str(exc.value)
    assert "ConnectError" in str(exc.value)


def test_build_quick_replies_message_limita_titulo_e_quantidade():
    replies = [{"title": "x" * 30, "payload": f"qr:n1:q{i}"} for i in range(15)]
    msg = instagram_api.build_quick_replies_message("Quer?", replies)
    assert msg["text"] == "Quer?" and len(msg["quick_replies"]) == 13
    assert msg["quick_replies"][0] == {"content_type": "text", "title": "x" * 20, "payload": "qr:n1:q0"}


def test_build_image_message():
    assert instagram_api.build_image_message("https://x.com/a.png") == {
        "attachment": {"type": "image", "payload": {"url": "https://x.com/a.png"}}
    }


async def test_send_quick_replies_e_send_image_usam_header_e_o_destinatario_certo(mock_meta):
    import json
    calls, _ = mock_meta
    await instagram_api.send_quick_replies(
        "123", {"id": "456"}, "Quer?", [{"title": "Sim", "payload": "qr:n1:q1"}], TOKEN)
    await instagram_api.send_quick_replies(
        "123", {"comment_id": "c1"}, "Quer?", [{"title": "Sim", "payload": "qr:n1:q1"}], TOKEN)
    await instagram_api.send_image("123", "456", "https://x.com/a.png", TOKEN)
    bodies = [json.loads(c.content) for c in calls]
    assert bodies[0]["recipient"] == {"id": "456"} and "quick_replies" in bodies[0]["message"]
    assert bodies[1]["recipient"] == {"comment_id": "c1"}
    assert bodies[2]["message"]["attachment"]["type"] == "image"
    for req in calls:
        _assert_token_no_header_e_fora_da_url(req)
