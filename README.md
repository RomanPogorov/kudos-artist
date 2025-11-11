# 🤖 Telegram Badge Bot - Полное руководство

Автоматическая генерация бейджей с вашим LoRA стилем через Telegram.

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Подробная настройка](#подробная-настройка)
3. [Обучение LoRA](#обучение-lora)
4. [Запуск бота](#запуск-бота)
5. [Деплой на сервер](#деплой-на-сервер)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 Быстрый старт

### Шаг 1: Создайте Telegram бота

1. Найдите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям (имя и username)
4. Сохраните токен (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Шаг 2: Получите Replicate API токен

1. Зарегистрируйтесь на [replicate.com](https://replicate.com)
2. Перейдите в [Account Settings](https://replicate.com/account/api-tokens)
3. Создайте новый токен
4. Сохраните его (начинается с `r8_...`)

### Шаг 3: Установите зависимости

```bash
pip install -r requirements.txt
```

### Шаг 4: Настройте бота

Откройте `badge_bot.py` и замените:

```python
TELEGRAM_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Ваш токен от BotFather
REPLICATE_API_TOKEN = "r8_xxxxxxxxxxxxx"  # Ваш токен от Replicate
LORA_MODEL = "username/your-model-name"  # Ваша обученная модель
```

### Шаг 5: Запустите

```bash
python badge_bot.py
```

---

## 📚 Подробная настройка

### Структура проекта

```
badge_bot/
├── badge_bot.py           # Основной файл бота
├── requirements.txt       # Зависимости Python
├── .env.example          # Пример конфигурации
├── fonts/                # Папка для шрифтов (опционально)
│   └── custom_font.ttf
└── README.md             # Эта инструкция
```

### Переменные окружения (опционально)

Вместо хардкода токенов, можно использовать `.env`:

```bash
# Создайте .env файл
cp .env.example .env

# Отредактируйте .env
nano .env
```

Затем измените начало `badge_bot.py`:

```python
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
LORA_MODEL = os.getenv("LORA_MODEL")
```

И установите `python-dotenv`:
```bash
pip install python-dotenv
```

---

## 🎨 Обучение LoRA

### Подготовка датасета

1. **Соберите 15-25 изображений вашего стиля**
   - Одинаковый персонаж
   - Разные объекты в руках
   - Чистый фон
   - Размер: 1024x1024px

2. **Структура:**
   ```
   training_images/
   ├── image_001.png
   ├── image_002.png
   ├── image_003.png
   ...
   └── image_015.png
   ```

3. **Требования к качеству:**
   - PNG формат
   - Без текста на изображениях
   - Хорошее освещение
   - Высокое разрешение

### Обучение через Replicate

```python
import replicate

# Упакуйте изображения в ZIP
# zip -r training_images.zip training_images/

# Загрузите архив на хостинг (например, на Google Drive или Dropbox)
# Получите прямую ссылку на скачивание

# Запустите обучение
training = replicate.trainings.create(
    version="ostris/flux-dev-lora-trainer:4ffd32160efd92e956d39c5338a9b8fbafca58e03f791f6d8011f3e20e8ea6fa",
    input={
        "input_images": "https://example.com/training_images.zip",
        "trigger_word": "aidbox_samurai_style",  # Ваше уникальное слово
        "steps": 1000,
        "learning_rate": 0.0004,
    },
    destination="your-username/samurai-badge-lora"  # Название модели
)

print(f"Training ID: {training.id}")
print(f"Status: {training.status}")

# Проверка статуса
training.reload()
print(f"Status: {training.status}")
```

**Ожидаемое время:** 30-60 минут

**Стоимость:** ~$2-5

### Альтернатива: Scenario.gg (No-code)

1. Перейдите на [scenario.gg](https://scenario.gg)
2. Загрузите изображения
3. Нажмите "Train Model"
4. Дождитесь завершения
5. Получите API endpoint

---

## 🎯 Запуск бота

### Локальный запуск

```bash
# Базовый запуск
python badge_bot.py

# С логами в файл
python badge_bot.py > bot.log 2>&1

# В фоновом режиме (Linux/Mac)
nohup python badge_bot.py &
```

### Тестирование

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Следуйте инструкциям

**Примеры команд:**

```
/start          - Начало работы
/create         - Создать новый бейдж
/help           - Справка
/examples       - Примеры запросов
/cancel         - Отменить создание

# Или просто напишите:
"лупу"          - Начнёт диалог
"меч | DEBUG NINJA" - Быстрая генерация
```

---

## 🚀 Деплой на сервер

### Вариант 1: VPS (DigitalOcean, AWS, etc)

```bash
# 1. Подключитесь к серверу
ssh root@your-server-ip

# 2. Установите Python 3.10+
sudo apt update
sudo apt install python3.10 python3-pip

# 3. Клонируйте проект
git clone https://github.com/yourusername/badge-bot.git
cd badge-bot

# 4. Установите зависимости
pip3 install -r requirements.txt

# 5. Настройте конфигурацию
nano badge_bot.py  # Укажите токены

# 6. Создайте systemd сервис
sudo nano /etc/systemd/system/badge-bot.service
```

**Содержимое сервиса:**

```ini
[Unit]
Description=Telegram Badge Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/badge-bot
ExecStart=/usr/bin/python3 /root/badge-bot/badge_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 7. Запустите сервис
sudo systemctl daemon-reload
sudo systemctl enable badge-bot
sudo systemctl start badge-bot

# 8. Проверьте статус
sudo systemctl status badge-bot

# 9. Просмотр логов
sudo journalctl -u badge-bot -f
```

### Вариант 2: Heroku

```bash
# 1. Создайте Procfile
echo "worker: python badge_bot.py" > Procfile

# 2. Создайте runtime.txt
echo "python-3.10.12" > runtime.txt

# 3. Инициализируйте git
git init
git add .
git commit -m "Initial commit"

# 4. Создайте приложение
heroku create your-badge-bot

# 5. Установите переменные окружения
heroku config:set TELEGRAM_TOKEN=your_token
heroku config:set REPLICATE_API_TOKEN=your_token
heroku config:set LORA_MODEL=your_model

# 6. Деплой
git push heroku main

# 7. Запустите worker
heroku ps:scale worker=1

# 8. Логи
heroku logs --tail
```

### Вариант 3: Docker

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY badge_bot.py .

CMD ["python", "badge_bot.py"]
```

```bash
# Сборка
docker build -t badge-bot .

# Запуск
docker run -d \
  --name badge-bot \
  --restart unless-stopped \
  -e TELEGRAM_TOKEN=your_token \
  -e REPLICATE_API_TOKEN=your_token \
  -e LORA_MODEL=your_model \
  badge-bot

# Логи
docker logs -f badge-bot
```

---

## 🔧 Настройка стиля

### Изменение шрифта

```python
# В badge_bot.py найдите:
FONT_PATH = "/path/to/your/custom/font.ttf"
FONT_SIZE = 48

# Рекомендуемые шрифты:
# - Impact (bold, классический)
# - Bebas Neue (современный)
# - Bangers (игровой)
# - Anton (жирный)
```

**Где взять шрифты:**
- [Google Fonts](https://fonts.google.com)
- [DaFont](https://www.dafont.com)
- [Font Squirrel](https://www.fontsquirrel.com)

### Изменение цветов

```python
TEXT_COLOR = "#4A3728"        # Цвет текста (темно-коричневый)
TEXT_STROKE_COLOR = "#F4C542" # Обводка текста (золотой)
BANNER_COLOR = "#F4C542"      # Фон баннера (золотой)

# Примеры палитр:
# Синяя: TEXT_COLOR="#1a237e", BANNER_COLOR="#42a5f5"
# Красная: TEXT_COLOR="#b71c1c", BANNER_COLOR="#ef5350"
# Зелёная: TEXT_COLOR="#1b5e20", BANNER_COLOR="#66bb6a"
```

### Тонкая настройка промпта

```python
BASE_PROMPT_TEMPLATE = (
    f"{TRIGGER_WORD}, "
    f"samurai warrior badge, "
    f"character holding {{object}}, "
    f"cartoon illustration, "
    f"flat colors, "
    f"white background, "
    f"centered composition, "
    f"game asset style"
)

# Добавьте детали для вашего стиля:
# - "anime style" для аниме
# - "pixel art" для пиксельной графики
# - "watercolor painting" для акварели
# - "3D render" для 3D стиля
```

---

## 🐛 Troubleshooting

### Проблема: "Error generating image"

**Причины:**
1. Неправильный токен Replicate
2. LoRA модель не обучена или недоступна
3. Закончились кредиты на Replicate

**Решение:**
```bash
# Проверьте токен
echo $REPLICATE_API_TOKEN

# Проверьте модель
replicate models list

# Проверьте баланс на replicate.com/account
```

### Проблема: "Font not found"

**Решение:**
```python
# Используйте дефолтный шрифт
FONT_PATH = None  # Бот автоматически переключится на default

# Или установите шрифты
# Ubuntu/Debian:
sudo apt install fonts-dejavu fonts-liberation

# macOS:
brew tap homebrew/cask-fonts
brew install font-dejavu
```

### Проблема: Текст не помещается на баннере

**Решение:**
```python
# Уменьшите размер шрифта
FONT_SIZE = 40  # Вместо 48

# Или ограничьте длину текста
if len(badge_text) > 15:
    badge_text = badge_text[:15]
```

### Проблема: Бот не отвечает

**Проверьте:**
```bash
# Работает ли скрипт?
ps aux | grep badge_bot.py

# Есть ли ошибки в логах?
tail -f bot.log

# Доступен ли Telegram API?
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Проблема: Медленная генерация

**Оптимизация:**
```python
# Уменьшите количество шагов
"num_inference_steps": 20,  # Вместо 30

# Используйте более быструю модель
# Flux вместо SDXL, если доступно
```

---

## 💡 Продвинутые фичи

### Добавление базы данных

```python
import sqlite3

# Создание БД для статистики
conn = sqlite3.connect('bot_stats.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        object TEXT,
        badge_text TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Логирование генераций
cursor.execute(
    "INSERT INTO generations (user_id, object, badge_text) VALUES (?, ?, ?)",
    (user_id, object_description, badge_text)
)
conn.commit()
```

### Добавление оплаты (Stripe)

```python
from telegram import LabeledPrice
from telegram.ext import PreCheckoutQueryHandler

async def send_invoice(update, context):
    await update.message.reply_invoice(
        title="Premium Badge Generation",
        description="10 badge generations",
        payload="badge-pack-10",
        provider_token="YOUR_STRIPE_TOKEN",
        currency="USD",
        prices=[LabeledPrice("10 Badges", 500)]  # $5.00
    )
```

### Добавление очереди (для высокой нагрузки)

```python
from celery import Celery

app = Celery('badge_bot', broker='redis://localhost:6379')

@app.task
def generate_badge_async(user_id, object_desc, badge_text):
    # Генерация в фоне
    pass
```

---

## 📊 Мониторинг

### Prometheus метрики

```python
from prometheus_client import Counter, Histogram, start_http_server

# Метрики
generations_total = Counter('badge_generations_total', 'Total badge generations')
generation_duration = Histogram('badge_generation_duration_seconds', 'Generation duration')

# Запуск метрик
start_http_server(8000)

# Использование
generations_total.inc()
with generation_duration.time():
    generate_image_with_lora(...)
```

### Логирование в файл

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
logging.getLogger().addHandler(handler)
```

---

## 📈 Масштабирование

### Для больших нагрузок

1. **Используйте Redis для кеша**
```python
import redis
cache = redis.Redis(host='localhost', port=6379)
```

2. **Балансировка нагрузки**
```bash
# Запустите несколько инстансов бота
python badge_bot.py &
python badge_bot.py &
python badge_bot.py &
```

3. **Webhook вместо polling**
```python
application.run_webhook(
    listen="0.0.0.0",
    port=8443,
    url_path="your_token",
    webhook_url="https://your-domain.com/your_token"
)
```

---

## 📝 Лицензия

MIT License - используйте свободно!

---

## 🤝 Поддержка

- GitHub Issues: [your-repo/issues]
- Telegram: [@yourusername]
- Email: your@email.com

---

## 🎉 Готово!

Ваш бот готов к работе! 

**Следующие шаги:**
1. ✅ Обучите LoRA на своём стиле
2. ✅ Настройте токены в коде
3. ✅ Запустите бота
4. ✅ Протестируйте генерацию
5. ✅ Задеплойте на сервер

Успехов! 🚀
