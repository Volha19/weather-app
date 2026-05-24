FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .