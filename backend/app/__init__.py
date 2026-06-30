"""Pacote da aplicação InboxPilot.

No Windows, o asyncio usa por padrão o ProactorEventLoop, que o psycopg
(async) não suporta. Forçamos o SelectorEventLoop ANTES de qualquer loop
ser criado (uvicorn ou scripts). Em Linux/macOS (deploy) isto é no-op.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
