FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY init_app.py .
COPY init.sql .
COPY templates/ ./templates/
COPY static/ ./static/
COPY tests/ ./tests/

RUN mkdir -p /app/logs

EXPOSE 80

CMD ["sh", "-c", "python init_app.py && python app.py"]