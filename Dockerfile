FROM python:3.10-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python пакетов
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY badge_bot.py .

# Создание директории для логов
RUN mkdir -p /app/logs

# Запуск бота
CMD ["python", "-u", "badge_bot.py"]
