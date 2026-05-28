FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MONGO_URI=mongodb://mongo:27017/market_anomaly \
    MONGO_DATABASE=market_anomaly

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system .

ENTRYPOINT ["market-watch"]
CMD ["--help"]
