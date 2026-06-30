"""Launcher de desenvolvimento.

No Windows o uvicorn usa por padrão o ProactorEventLoop, incompatível com o
psycopg em modo async. Aqui criamos um SelectorEventLoop e rodamos o servidor
diretamente nele (via server.serve()), contornando o setup de loop do uvicorn.

Em Linux/macOS (deploy Railway/Render) cai no asyncio.run normal — por isso o
Dockerfile/Procfile podem seguir usando `uvicorn app.main:app`.

Uso:  python run.py
"""

import asyncio
import selectors
import sys

import uvicorn


def main() -> None:
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
