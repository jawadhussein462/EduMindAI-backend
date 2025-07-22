FROM python:3.9-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./api /app/api
COPY ./.chroma_db /app/.chroma_db

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "80"]