FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /shared \
    && chown -R appuser:appuser /app /shared

USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8501
VOLUME ["/shared"]

CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
