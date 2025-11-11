# Kudos Artist 🎨

Telegram бот для генерации кастомных бейджей с помощью **Google Nano Banana** (Gemini Image Generation) через Replicate API.

## 🌟 Возможности

- 🎨 Генерация изображений через модель `google/nano-banana`
- 🖼️ Поддержка референсных изображений для стилизации
- 📝 Добавление красивого текстового баннера на бейдж
- 🌍 Автоматический перевод промптов с русского на английский
- ⚡ Простой диалоговый интерфейс

## 🚀 Быстрый старт

### Требования

- Python 3.8+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))
- Replicate API Token (с [replicate.com](https://replicate.com/account/api-tokens))

### Установка

```bash
# Клонируй репозиторий
git clone https://github.com/RomanPogorov/kudos-artist.git
cd kudos-artist

# Установи зависимости
pip install -r requirements.txt

# Создай .env файл с токенами
cat > .env << EOF
TELEGRAM_TOKEN=your_telegram_token
REPLICATE_API_TOKEN=your_replicate_token
EOF

# Загрузи переменные и запусти
export $(cat .env | xargs) && python badge_bot.py
```

## 📝 Использование

1. Запусти бота командой `/start` или `/create`
2. Опиши сюжет/сцену для картинки (например: "самурай с мечом")
3. Укажи текст для баннера (например: "CODE NINJA")
4. Получи готовый бейдж!

### Примеры промптов

- "самурай в боевой стойке с мечом"
- "самурай с луной на фоне"
- "plays the guitar"
- "ninja in meditation"

## 🛠️ Технологии

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [Replicate](https://replicate.com/) - API для ML моделей
- [Google Nano Banana](https://replicate.com/google/nano-banana) - Gemini Image Generation
- [Pillow](https://python-pillow.org/) - Обработка изображений
- [deep-translator](https://github.com/nidhaloff/deep-translator) - Перевод текста

## ⚙️ Конфигурация

Настройки в `badge_bot.py`:

```python
GENERATION_MODEL = "google/nano-banana"
GENERATION_SEED = 4034097716  # Фиксированный seed
REFERENCE_IMAGES_DIR = "reference_images"  # Папка с референсами
```

### Референсные изображения

Положи свои референсные фото в папку `reference_images/`. Бот автоматически использует их для стилизации.

## 📦 Docker

```bash
docker-compose up -d
```

## 📄 Лицензия

MIT

## 🤝 Контрибьюция

Pull requests приветствуются!

---

Сделано с ❤️ используя Google Nano Banana
