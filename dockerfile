FROM python:3.12-slim

# Будут видны только ошибки и предупреждения, а не отладочная информация
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

# Просто создание папочки
WORKDIR /code

# no-cache-dir - не сохранять кэш при установке пакетов, чтобы уменьшить размер образа
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# копирует все папочки в папку code внутри контейнера
COPY . .