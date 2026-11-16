"""Recifra todos os tokens com a chave mais nova de TOKEN_ENCRYPTION_KEYS.

Rotação de chave:
  1. Gere uma chave nova e coloque-a NA FRENTE:  TOKEN_ENCRYPTION_KEYS=nova,antiga
  2. Faça deploy (o app já decifra com as duas).
  3. Rode:  python -m scripts.rotate_token_key
  4. Remova a antiga:  TOKEN_ENCRYPTION_KEYS=nova
"""

import asyncio

from sqlalchemy import select

from app.core import crypto
from app.core.database import SessionLocal
from app.models.account import InstagramAccount


async def main() -> None:
    async with SessionLocal() as db:
        accounts = (await db.execute(select(InstagramAccount))).scalars().all()
        for account in accounts:
            account.access_token_enc = crypto.rotate(account.access_token_enc)
        await db.commit()
    print(f"{len(accounts)} token(s) recifrado(s) com a chave atual.")


if __name__ == "__main__":
    asyncio.run(main())
