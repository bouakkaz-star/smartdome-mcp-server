# --- ТОВА ЛИПСВАШЕ ---
FROM python:3.11-slim

WORKDIR /app
# ---------------------

# Обновяване на pip (за всеки случай)
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT 8080
ENV PYTHONPATH="${PYTHONPATH}:/app/app"

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
