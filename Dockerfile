FROM python:3.11-slim

WORKDIR /app

COPY packages /packages
COPY requirements.txt .

RUN pip install --no-index --find-links=/packages -r requirements.txt

COPY . .

ENV COURSE_NAME=python
EXPOSE 8003

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8003"]