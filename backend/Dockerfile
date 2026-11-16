FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway/Render injetam a porta via $PORT.
ENV PORT=8000
EXPOSE 8000

# Aplica as migrações pendentes antes de subir (o plano free do Render não tem
# pre-deploy command). Se a migração falhar, o container não sobe — e o
# Postgres desfaz a migração inteira (DDL transacional).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
