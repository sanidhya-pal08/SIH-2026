FROM python:3.11-slim

WORKDIR /app

# Layer-cache: install deps before copying source
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY database.py graph_engine.py main.py ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
