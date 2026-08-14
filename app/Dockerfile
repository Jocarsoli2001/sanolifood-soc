FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv \
    && addgroup --system --gid 10001 sanolifood \
    && adduser --system --uid 10001 --ingroup sanolifood --home /app sanolifood

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip \
    && pip install ".[test]"

COPY alembic.ini ./
COPY migrations ./migrations
COPY templates ./templates
COPY static ./static
COPY tests ./tests
COPY entrypoint.sh ./entrypoint.sh

RUN chmod 0555 /app/entrypoint.sh \
    && chown -R sanolifood:sanolifood /app

USER 10001:10001

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "sanolifood.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
