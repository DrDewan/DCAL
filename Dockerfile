FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 dcal \
    && useradd --system --uid 10001 --gid dcal --home-dir /app dcal \
    && mkdir -p /app/data/images /app/data/state \
    && chown -R dcal:dcal /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY docker/dcal-entrypoint.sh /usr/local/bin/dcal-entrypoint
RUN chmod 0755 /usr/local/bin/dcal-entrypoint \
    && python -m pip install --no-cache-dir .

ENTRYPOINT ["/usr/local/bin/dcal-entrypoint"]
CMD ["watch", "--interval", "60"]
