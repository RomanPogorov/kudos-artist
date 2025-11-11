"""
Telegram Bot для автоматической генерации бейджей с Nonabana
Пользователь пишет текст → бот генерирует картинку с использованием reference images
"""

import os
import logging
import requests
import tempfile
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import replicate
from replicate.exceptions import ReplicateError
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from dotenv import load_dotenv
import numpy as np

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ - ЗАМЕНИТЕ НА СВОИ ЗНАЧЕНИЯ
# =============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")  # От @BotFather
# Токен Replicate можно задать через переменную окружения REPLICATE_API_TOKEN
# или здесь (переменная окружения имеет приоритет)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "YOUR_REPLICATE_TOKEN")
# Модель для генерации изображений
GENERATION_MODEL = "google/nano-banana"  # Модель Nano Banana от Google для работы с reference images
# Seed для генерации (None = случайный, число = фиксированный seed)
GENERATION_SEED = 4034097716  # Фиксированный seed для консистентности

# Путь к папке с референсными фото (предустановленные)
REFERENCE_IMAGES_DIR = "reference_images"  # Папка с референсными фото в проекте
USE_PREDEFINED_REFERENCE_IMAGES = True  # Использовать предустановленные фото вместо загрузки пользователем

# Настройки промпта (Nano Banana работает с естественным языком)
NEGATIVE_PROMPT = "text, letters, words, signature, watermark, realistic, photo, multiple characters, blurry"

# Настройки текста на бейдже
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Путь к шрифту
FONT_SIZE_BASE = 60  # Базовый размер шрифта для текста на баннере
FONT_SIZE_MIN = 30  # Минимальный размер шрифта
FONT_SIZE_MAX = 80  # Максимальный размер шрифта
TEXT_COLOR = "#4A3728"  # Темно-коричневый
TEXT_STROKE_COLOR = "#000000"  # Чёрная обводка для контраста
TEXT_STROKE_WIDTH = 3  # Толщина обводки текста
# Позиция текста на баннере (процент от высоты изображения)
TEXT_Y_POSITION_PERCENT = 0.93  # 93% от высоты = примерно на баннере внизу

# Состояния диалога
WAITING_FOR_SCENE, WAITING_FOR_BADGE_TEXT, WAITING_FOR_REFERENCE_PHOTOS = range(3)

# =============================================================================
# ФУНКЦИИ ГЕНЕРАЦИИ
# =============================================================================

def find_yellow_banner_center(img: Image.Image, user_id: int) -> tuple:
    """
    Находит центр жёлтого баннера на изображении по цвету
    
    Args:
        img: PIL Image объект
        user_id: ID пользователя для логирования
        
    Returns:
        Кортеж (center_x, center_y) с координатами центра баннера
    """
    try:
        # Конвертируем изображение в numpy массив
        img_array = np.array(img)
        
        # Ищем только в нижней половине изображения (баннер всегда внизу)
        height = img_array.shape[0]
        width = img_array.shape[1]
        search_area = img_array[int(height * 0.6):, :]  # Нижние 40%
        
        # Определяем диапазон жёлтого цвета (RGB)
        # Жёлтый баннер примерно #F4C542 = RGB(244, 197, 66)
        lower_yellow = np.array([200, 160, 40])  # Нижняя граница
        upper_yellow = np.array([255, 220, 100])  # Верхняя граница
        
        # Создаём маску для жёлтых пикселей
        mask = np.all((search_area >= lower_yellow) & (search_area <= upper_yellow), axis=-1)
        
        # Находим координаты всех жёлтых пикселей
        yellow_pixels = np.where(mask)
        
        if len(yellow_pixels[0]) > 0:
            # Вычисляем центр масс жёлтой области
            center_y = int(np.mean(yellow_pixels[0])) + int(height * 0.6)  # Добавляем отступ
            center_x = int(np.mean(yellow_pixels[1]))
            
            logger.info(f"User {user_id}: Found yellow banner at ({center_x}, {center_y}), yellow pixels: {len(yellow_pixels[0])}")
            return (center_x, center_y)
        else:
            # Если не нашли жёлтый баннер, используем позицию по умолчанию
            logger.warning(f"User {user_id}: Yellow banner not found, using default position")
            return (width // 2, int(height * 0.93))
            
    except Exception as e:
        logger.error(f"User {user_id}: Error finding yellow banner: {e}")
        # Fallback к позиции по умолчанию
        return (img.width // 2, int(img.height * 0.93))

def load_reference_images_from_dir(directory: str) -> list:
    """
    Загружает референсные фото из указанной папки
    
    Args:
        directory: Путь к папке с референсными фото
        
    Returns:
        Список BytesIO объектов с изображениями
    """
    reference_images = []
    
    if not os.path.exists(directory):
        logger.warning(f"Directory {directory} does not exist, skipping reference images")
        return reference_images
    
    # Поддерживаемые форматы изображений
    supported_formats = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    
    try:
        # Получаем список файлов в папке
        files = [f for f in os.listdir(directory) 
                if os.path.isfile(os.path.join(directory, f)) 
                and f.lower().endswith(supported_formats)]
        
        # Сортируем для консистентности
        files.sort()
        
        for filename in files:
            filepath = os.path.join(directory, filename)
            try:
                # Открываем изображение и конвертируем в BytesIO
                with open(filepath, 'rb') as f:
                    img_bytes = BytesIO(f.read())
                    img_bytes.seek(0)
                    reference_images.append(img_bytes)
                    logger.info(f"Loaded reference image: {filename}")
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        
        logger.info(f"Loaded {len(reference_images)} reference image(s) from {directory}")
        
    except Exception as e:
        logger.error(f"Error loading reference images from {directory}: {e}")
    
    return reference_images


def translate_to_english(text: str, user_id: int) -> str:
    """
    Переводит текст с русского на английский
    
    Args:
        text: Текст для перевода
        user_id: ID пользователя для логирования
        
    Returns:
        Переведённый текст на английском
    """
    try:
        # Проверяем, есть ли кириллица (русские буквы)
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
        
        if has_cyrillic:
            logger.info(f"User {user_id}: Translating '{text}' from Russian to English")
            translator = GoogleTranslator(source='ru', target='en')
            translated = translator.translate(text)
            logger.info(f"User {user_id}: Translated to '{translated}'")
            return translated
        else:
            # Если нет кириллицы, возвращаем как есть
            return text
    except Exception as e:
        logger.warning(f"User {user_id}: Translation failed: {e}, using original text")
        return text

def generate_image_with_lora(scene_description: str, user_id: int, reference_images: list = None) -> str:
    """
    Генерирует изображение через модель google/nano-banana
    
    Args:
        scene_description: Описание сюжета/сцены для генерации
        user_id: ID пользователя для логирования
        reference_images: Список URL или BytesIO объектов с референсными изображениями
        
    Returns:
        URL сгенерированного изображения
    """
    # Убеждаемся, что токен установлен
    if not os.getenv("REPLICATE_API_TOKEN"):
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    model_name = GENERATION_MODEL  # Используем модель google/nano-banana
    
    try:
        logger.info(f"User {user_id}: Generating image with scene description '{scene_description}'")
        logger.info(f"User {user_id}: Using model: {model_name}")
        if reference_images:
            logger.info(f"User {user_id}: Using {len(reference_images)} reference image(s)")
        
        # Формируем промпт без триггерного слова
        prompt = scene_description
        logger.info(f"User {user_id}: Prompt: {prompt}")
        logger.info(f"User {user_id}: Seed: {GENERATION_SEED}")
        
        # Формируем параметры для модели google/nano-banana
        # Nano Banana принимает prompt и image_input (массив) для reference images
        nano_banana_input = {
            "prompt": prompt,
            "output_format": "jpg",  # Формат выходного файла
        }
        
        # Добавляем reference images если они есть
        # Nano Banana поддерживает multi-image fusion
        # Передаём BytesIO объекты или URL напрямую в image_input
        if reference_images:
            image_inputs = []
            
            # Обрабатываем все референсные изображения
            for ref_image in reference_images:
                # Если это BytesIO, сбрасываем позицию и передаём напрямую
                if isinstance(ref_image, BytesIO):
                    ref_image.seek(0)
                    image_inputs.append(ref_image)
                    logger.info(f"User {user_id}: Added BytesIO reference image")
                else:
                    # Если это URL или другой формат
                    image_inputs.append(ref_image)
                    logger.info(f"User {user_id}: Added reference image (URL): {ref_image}")
            
            # Добавляем изображения в параметр
            # Согласно документации API, параметр называется "image_input" и это массив
            if image_inputs:
                nano_banana_input["image_input"] = image_inputs
                # Используем aspect_ratio для соответствия входному изображению
                nano_banana_input["aspect_ratio"] = "match_input_image"
                logger.info(f"User {user_id}: Added {len(image_inputs)} reference image(s) to 'image_input' parameter")
        
        # Добавляем seed если указан
        if GENERATION_SEED is not None:
            nano_banana_input["seed"] = int(GENERATION_SEED)
        
        logger.info(f"User {user_id}: Nano Banana input params: prompt='{prompt[:100]}', has_image_input={'image_input' in nano_banana_input}, seed={nano_banana_input.get('seed', 'None')}, aspect_ratio={nano_banana_input.get('aspect_ratio', 'N/A')}")
        
        output = replicate.run(
            model_name,
            input=nano_banana_input
        )
        
        # Для google/nano-banana output - это FileOutput объект с методами .url() и .read()
        # Согласно документации: output.url() возвращает URL файла
        if hasattr(output, 'url'):
            image_url = output.url()
            logger.info(f"User {user_id}: Image generated successfully (FileOutput): {str(image_url)[:50]}...")
        else:
            # Fallback для других моделей (возвращают список)
            image_url = output[0] if isinstance(output, list) else output
            logger.info(f"User {user_id}: Image generated successfully (legacy): {str(image_url)[:50]}...")
        
        logger.info(f"User {user_id}: Used seed: {GENERATION_SEED} (from config)")
        return image_url
        
    except ReplicateError as e:
        error_detail = str(e)
        logger.error(f"User {user_id}: ReplicateError occurred")
        logger.error(f"User {user_id}: model_name = {model_name}")
        logger.error(f"User {user_id}: GENERATION_MODEL = {GENERATION_MODEL}")
        logger.error(f"User {user_id}: Full error: {error_detail}")
        
        if "404" in error_detail or "not found" in error_detail.lower():
            error_msg = (
                f"❌ Модель не найдена (404)\n\n"
                f"Модель '{GENERATION_MODEL}' не существует в Replicate.\n\n"
                f"Проверьте модель на: https://replicate.com/{GENERATION_MODEL.split(':')[0]}"
            )
        else:
            error_msg = f"❌ Ошибка Replicate API: {error_detail}"
        
        logger.error(f"User {user_id}: ReplicateError Details:\n{error_detail}")
        raise ValueError(error_msg) from e
        
    except Exception as e:
        logger.error(f"User {user_id}: Error generating image: {e}")
        raise


def draw_text_on_arc(img, draw, text: str, font, center_x: int, center_y: int, radius: int, 
                     start_angle: float, end_angle: float, fill: str, stroke_fill: str = None, 
                     stroke_width: int = 0):
    """
    Рисует текст по дуге с поворотом символов
    
    Args:
        img: Image объект для вставки повёрнутых символов
        draw: ImageDraw объект
        text: Текст для рисования
        font: Шрифт
        center_x, center_y: Центр дуги
        radius: Радиус дуги
        start_angle: Начальный угол в радианах
        end_angle: Конечный угол в радианах
        fill: Цвет текста
        stroke_fill: Цвет обводки
        stroke_width: Толщина обводки
    """
    import math
    
    # Вычисляем угол для каждого символа
    angle_range = end_angle - start_angle
    char_count = len(text)
    
    for i, char in enumerate(text):
        # Вычисляем угол для текущего символа
        char_angle = start_angle + (angle_range / (char_count + 1)) * (i + 1)
        
        # Вычисляем позицию символа на дуге
        x = center_x + radius * math.cos(char_angle)
        y = center_y + radius * math.sin(char_angle)
        
        # Поворачиваем символ по касательной к дуге
        # Угол поворота = угол дуги + 90 градусов (чтобы текст был перпендикулярен радиусу)
        rotation_angle = math.degrees(char_angle) + 90
        
        # Получаем размер символа
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]
        
        # Создаём временное изображение для поворота символа
        padding = max(char_width, char_height) + 20
        char_img = Image.new('RGBA', (padding, padding), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        
        # Рисуем символ в центре временного изображения
        char_x = (padding - char_width) // 2
        char_y = (padding - char_height) // 2
        char_draw.text((char_x, char_y), char, font=font, fill=fill, 
                      stroke_fill=stroke_fill if stroke_fill else None, 
                      stroke_width=stroke_width)
        
        # Поворачиваем символ
        rotated_char = char_img.rotate(rotation_angle, expand=False, resample=Image.Resampling.BICUBIC)
        
        # Вычисляем позицию для вставки (центр повёрнутого символа)
        rot_width, rot_height = rotated_char.size
        paste_x = int(x - rot_width / 2)
        paste_y = int(y - rot_height / 2)
        
        # Вставляем повёрнутый символ на основное изображение
        img.paste(rotated_char, (paste_x, paste_y), rotated_char)


def add_text_to_badge(image_url: str, badge_text: str, user_id: int) -> BytesIO:
    """
    Добавляет текст на баннер бейджа
    
    Args:
        image_url: URL сгенерированного изображения
        badge_text: Текст для баннера
        user_id: ID пользователя
        
    Returns:
        BytesIO объект с готовым изображением
    """
    try:
        logger.info(f"User {user_id}: Adding text '{badge_text}' to badge")
        
        # Загружаем изображение
        response = requests.get(image_url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        
        # Конвертируем в RGB если нужно (для работы с RGBA)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Конвертируем в RGBA для поддержки прозрачности баннера
        img = img.convert('RGBA')
        
        # Подготовка для рисования
        draw = ImageDraw.Draw(img)
        
        # Приводим текст к uppercase для стиля
        badge_text = badge_text.upper()
        
        # Вычисляем адаптивный размер шрифта в зависимости от размера изображения
        image_width = img.width
        image_height = img.height
        
        # Используем фиксированный размер, адаптированный к ширине изображения
        scale_factor = image_width / 1024  # 1024 - стандартная ширина от Nano Banana
        font_size = int(FONT_SIZE_BASE * scale_factor)
        # Ограничиваем диапазоном
        font_size = max(FONT_SIZE_MIN, min(font_size, FONT_SIZE_MAX))
        
        logger.info(f"User {user_id}: Image size: {img.width}x{img.height}, Scale factor: {scale_factor:.2f}, Font size: {font_size}")
        
        # Загружаем шрифт с адаптивным размером
        font = None
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
            logger.info(f"User {user_id}: Font loaded successfully: {FONT_PATH}, size: {font_size}")
        except Exception as e:
            logger.warning(f"User {user_id}: Custom font not found ({e}), trying to load default font")
            try:
                # Пробуем загрузить системный шрифт
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
                logger.info(f"User {user_id}: System font loaded, size: {font_size}")
            except Exception:
                logger.warning(f"User {user_id}: System font failed, using default")
                # Дефолтный шрифт PIL не поддерживает большие размеры, создаём временный файл
                font = ImageFont.load_default()
                # Для дефолтного шрифта увеличиваем размер через масштабирование
                logger.warning(f"User {user_id}: Using default font (limited size support)")
        
        if font is None:
            raise ValueError("Failed to load any font")
        
        # Вычисляем размеры текста
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Находим центр жёлтого баннера автоматически
        text_x, text_y = find_yellow_banner_center(img, user_id)
        logger.info(f"User {user_id}: Placing text at ({text_x}, {text_y})")
        
        # Рисуем текст с якорем в центре (mm = middle-middle)
        stroke_width = int(TEXT_STROKE_WIDTH * scale_factor)
        draw.text(
            (text_x, text_y),
            badge_text,
            font=font,
            fill=TEXT_COLOR,
            stroke_width=stroke_width,
            stroke_fill=TEXT_STROKE_COLOR,
            anchor="mm"  # Центрируем текст по середине
        )
        
        # Сохраняем в BytesIO
        output = BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)
        
        logger.info(f"User {user_id}: Badge completed successfully - Font: {font_size}px, Text at y={text_y}")
        return output
        
    except Exception as e:
        logger.error(f"User {user_id}: Error adding text to badge: {e}")
        raise


# =============================================================================
# ОБРАБОТЧИКИ КОМАНД
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я создаю бейджи с самураем в твоём уникальном стиле.

🎨 **Как это работает:**
1. Опиши сюжет/сцену для картинки
   Например: "самурай в боевой стойке с мечом", "самурай с луной на фоне"
2. Укажи текст для баннера на бейдже
   Например: "DEBUG NINJA", "CODE MASTER"
3. Получи готовый бейдж!

Просто напиши мне что-нибудь, и начнём! 🚀

Команды:
/create - Создать новый бейдж
/help - Помощь
/examples - Примеры запросов
"""
    await update.message.reply_text(welcome_text)
    return WAITING_FOR_SCENE


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📖 **Справка по использованию**

**Шаг 1:** Опиши сюжет/сцену для картинки
• Будь конкретным: "самурай в боевой стойке с мечом", "самурай с луной на фоне"
• Можно на русском или английском
• Опиши что должно быть на картинке

**Шаг 2:** Укажите текст для баннера
• До 20 символов для лучшего вида
• Английские заглавные буквы смотрятся лучше
• Примеры: "UX SCOUT", "DEBUG NINJA"

⏱ Генерация занимает 10-30 секунд

💡 Если результат не понравился, просто начните заново!
"""
    await update.message.reply_text(help_text)


async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /examples"""
    examples_text = """
💡 **Примеры хороших запросов:**

**Для сюжета:**
✅ "самурай в боевой стойке с мечом"
✅ "самурай с луной на фоне"
✅ "самурай в доспехах с катаной"
✅ "самурай в медитации"
✅ "самурай на фоне гор"
✅ "самурай с драконом"

**Для текста баннера:**
✅ "CODE SAMURAI"
✅ "UX NINJA"
✅ "DEBUG MASTER"
✅ "API WARRIOR"
✅ "DATA SENSEI"

❌ **Избегайте:**
- Слишком длинные описания сюжета
- Длинные тексты: "THE BEST DEVELOPER IN THE WORLD"
"""
    await update.message.reply_text(examples_text)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    await update.message.reply_text(
        "❌ Создание бейджа отменено.\n"
        "Используй /create чтобы начать заново!"
    )
    context.user_data.clear()
    return ConversationHandler.END


# =============================================================================
# ОСНОВНОЙ ДИАЛОГ СОЗДАНИЯ БЕЙДЖА
# =============================================================================

async def create_badge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания бейджа"""
    steps_text = "**Шаг 1/2:**" if USE_PREDEFINED_REFERENCE_IMAGES else "**Шаг 1/3:**"
    await update.message.reply_text(
        f"🎨 Создаём новый бейдж!\n\n"
        f"{steps_text} Опиши сюжет/сцену для картинки\n"
        f"Например: самурай в боевой стойке с мечом, самурай с луной на фоне...\n\n"
        f"Или /cancel для отмены"
    )
    return WAITING_FOR_SCENE


async def handle_scene_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания сюжета"""
    user_id = update.effective_user.id
    scene_description = update.message.text.strip()
    
    # Переводим на английский если нужно
    scene_description_en = translate_to_english(scene_description, user_id)
    
    # Сохраняем переведённый текст в контекст
    context.user_data['scene'] = scene_description_en
    context.user_data['scene_original'] = scene_description  # Сохраняем оригинал для отображения
    
    display_text = scene_description if scene_description == scene_description_en else f"{scene_description} ({scene_description_en})"
    
    # Если используем предустановленные фото, загружаем их
    if USE_PREDEFINED_REFERENCE_IMAGES:
        reference_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
        context.user_data['reference_images'] = reference_images
        
        if reference_images:
            await update.message.reply_text(
                f"✅ Отлично! Сюжет: *{display_text}*\n\n"
                f"📸 Использую предустановленные референсные фото ({len(reference_images)} шт.)\n\n"
                f"**Шаг 2/2:** Какой текст написать на баннере?\n"
                f"Например: DEBUG NINJA, CODE MASTER, UX SCOUT...\n\n"
                f"(До 20 символов)",
                parse_mode='Markdown'
            )
            return WAITING_FOR_BADGE_TEXT
        else:
            await update.message.reply_text(
                f"✅ Отлично! Сюжет: *{display_text}*\n\n"
                f"⚠️ Референсные фото не найдены в папке {REFERENCE_IMAGES_DIR}\n\n"
                f"**Шаг 2/2:** Какой текст написать на баннере?\n"
                f"Например: DEBUG NINJA, CODE MASTER, UX SCOUT...\n\n"
                f"(До 20 символов)",
                parse_mode='Markdown'
            )
            return WAITING_FOR_BADGE_TEXT
    else:
        # Старый вариант - пользователь загружает фото
        await update.message.reply_text(
            f"✅ Отлично! Сюжет: *{display_text}*\n\n"
            f"**Шаг 2/3:** Хочешь добавить референсные фото? (опционально)\n"
            f"Отправь фото или напиши /skip чтобы пропустить\n\n"
            f"Можно отправить до 4 фото",
            parse_mode='Markdown'
        )
        
        # Инициализируем список для референсных фото
        context.user_data['reference_images'] = []
        
        return WAITING_FOR_REFERENCE_PHOTOS


async def handle_reference_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки референсных фото"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли фото в сообщении
    if update.message.photo:
        photos = update.message.photo
        # Берём фото наибольшего размера
        photo = photos[-1]
        
        # Получаем файл
        file = await context.bot.get_file(photo.file_id)
        
        # Скачиваем фото
        photo_bytes = BytesIO()
        await file.download_to_memory(photo_bytes)
        photo_bytes.seek(0)
        
        # Сохраняем в контекст
        if 'reference_images' not in context.user_data:
            context.user_data['reference_images'] = []
        
        # Сохраняем BytesIO объект
        context.user_data['reference_images'].append(photo_bytes)
        
        count = len(context.user_data['reference_images'])
        
        if count >= 4:
            await update.message.reply_text(
                f"✅ Загружено {count} фото (максимум)\n\n"
                f"**Шаг 3/3:** Какой текст написать на баннере?\n"
                f"Например: DEBUG NINJA, CODE MASTER, UX SCOUT...\n\n"
                f"(До 20 символов)",
                parse_mode='Markdown'
            )
            return WAITING_FOR_BADGE_TEXT
        else:
            await update.message.reply_text(
                f"✅ Фото {count}/4 загружено\n\n"
                f"Отправь ещё фото или напиши /skip чтобы перейти к тексту баннера"
            )
            return WAITING_FOR_REFERENCE_PHOTOS
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, отправь фото или используй /skip"
        )
        return WAITING_FOR_REFERENCE_PHOTOS


async def skip_reference_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск загрузки референсных фото"""
    await update.message.reply_text(
        "⏭ Пропускаем референсные фото\n\n"
        "**Шаг 3/3:** Какой текст написать на баннере?\n"
        "Например: DEBUG NINJA, CODE MASTER, UX SCOUT...\n\n"
        "(До 20 символов)",
        parse_mode='Markdown'
    )
    return WAITING_FOR_BADGE_TEXT


async def handle_badge_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для баннера и генерация финального бейджа"""
    user_id = update.effective_user.id
    badge_text = update.message.text.strip()
    
    # Проверка длины текста
    if len(badge_text) > 20:
        await update.message.reply_text(
            "⚠️ Текст слишком длинный (максимум 20 символов).\n"
            "Попробуй покороче:"
        )
        return WAITING_FOR_BADGE_TEXT
    
    scene_description = context.user_data.get('scene', 'unknown scene')
    reference_images = context.user_data.get('reference_images', [])
    
    # Уведомляем о начале генерации
    status_message = await update.message.reply_text(
        "⏳ Создаю твой бейдж...\n"
        "Это займёт 10-30 секунд ⚡"
    )
    
    try:
        # Шаг 1: Генерация изображения через google/nano-banana
        await status_message.edit_text(
            "⏳ Генерирую изображение... (1/2)"
        )
        image_url = generate_image_with_lora(scene_description, user_id, reference_images)
        
        # Шаг 2: Добавление текста
        await status_message.edit_text(
            "⏳ Добавляю текст на баннер... (2/2)"
        )
        final_image = add_text_to_badge(image_url, badge_text, user_id)
        
        # Отправляем готовый бейдж
        await status_message.delete()
        
        # Показываем оригинальный текст если был перевод
        original_scene = context.user_data.get('scene_original', scene_description)
        
        caption = f"🎊 Твой бейдж готов!\n\n" \
                  f"🎨 Сюжет: {original_scene}\n" \
                  f"📝 Текст: {badge_text}\n\n" \
                  f"Хочешь ещё? Просто напиши /create"
        
        await update.message.reply_photo(
            photo=final_image,
            caption=caption
        )
        
        logger.info(f"User {user_id}: Badge created successfully - '{original_scene}' ({scene_description}) + '{badge_text}'")
        
    except ValueError as e:
        # Ошибки конфигурации или модели
        error_msg = str(e)
        logger.error(f"User {user_id}: Configuration error: {error_msg}")
        await status_message.edit_text(error_msg)
        
    except Exception as e:
        logger.error(f"User {user_id}: Failed to create badge: {e}")
        error_detail = str(e)
        
        # Более конкретные сообщения для разных типов ошибок
        if "404" in error_detail or "not found" in error_detail.lower():
            user_message = (
                "❌ Модель не найдена\n\n"
                "Модель не существует в Replicate или недоступна.\n"
                "Проверьте настройку GENERATION_MODEL в коде бота."
            )
        elif "401" in error_detail or "unauthorized" in error_detail.lower():
            user_message = (
                "❌ Ошибка авторизации\n\n"
                "Проверьте правильность REPLICATE_API_TOKEN."
            )
        elif "429" in error_detail or "rate limit" in error_detail.lower():
            user_message = (
                "❌ Превышен лимит запросов\n\n"
                "Подождите минуту и попробуйте снова."
            )
        else:
            user_message = (
                "❌ Ошибка при создании бейджа.\n"
                "Попробуй ещё раз через /create\n\n"
                f"Если ошибка повторяется, попробуй:\n"
                f"• Упростить описание объекта\n"
                f"• Использовать другой текст\n"
                f"• Подождать минуту и попробовать снова"
            )
        
        await status_message.edit_text(user_message)
    
    # Очищаем данные пользователя
    context.user_data.clear()
    return ConversationHandler.END


async def handle_quick_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Быстрая генерация в одно сообщение
    Формат: "сюжет | текст" или просто "сюжет"
    """
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Парсим сообщение
    if '|' in message_text:
        parts = message_text.split('|')
        scene_description = parts[0].strip()
        badge_text = parts[1].strip() if len(parts) > 1 else "SAMURAI"
        # Переводим описание сюжета на английский
        scene_description_en = translate_to_english(scene_description, user_id)
    else:
        # Если нет разделителя, запускаем диалог
        # Переводим на английский если нужно
        scene_description_en = translate_to_english(message_text, user_id)
        context.user_data['scene'] = scene_description_en
        context.user_data['scene_original'] = message_text
        
        display_text = message_text if message_text == scene_description_en else f"{message_text} ({scene_description_en})"
        
        # Загружаем референсные изображения если используются предустановленные
        if USE_PREDEFINED_REFERENCE_IMAGES:
            reference_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
            context.user_data['reference_images'] = reference_images
            
            if reference_images:
                await update.message.reply_text(
                    f"✅ Сюжет: *{display_text}*\n\n"
                    f"📸 Использую предустановленные референсные фото ({len(reference_images)} шт.)\n\n"
                    f"Какой текст написать на баннере?",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"✅ Сюжет: *{display_text}*\n\n"
                    f"⚠️ Референсные фото не найдены\n\n"
                    f"Какой текст написать на баннере?",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text(
                f"✅ Сюжет: *{display_text}*\n\n"
                f"Какой текст написать на баннере?",
                parse_mode='Markdown'
            )
        
        return WAITING_FOR_BADGE_TEXT
    
    # Генерация
    status_message = await update.message.reply_text("⏳ Создаю бейдж...")
    
    # Загружаем референсные изображения если используются предустановленные
    reference_images = []
    if USE_PREDEFINED_REFERENCE_IMAGES:
        reference_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
    
    try:
        image_url = generate_image_with_lora(scene_description_en, user_id, reference_images)
        final_image = add_text_to_badge(image_url, badge_text, user_id)
        
        await status_message.delete()
        original_scene = context.user_data.get('scene_original', scene_description_en)
        await update.message.reply_photo(
            photo=final_image,
            caption=f"🎊 Готово!\n{original_scene} | {badge_text}"
        )
        
    except ValueError as e:
        # Ошибки конфигурации или модели
        error_msg = str(e)
        logger.error(f"User {user_id}: Configuration error: {error_msg}")
        await status_message.edit_text(error_msg)
        
    except Exception as e:
        logger.error(f"User {user_id}: Failed to create badge: {e}")
        error_detail = str(e)
        
        # Более конкретные сообщения для разных типов ошибок
        if "404" in error_detail or "not found" in error_detail.lower():
            user_message = (
                "❌ Модель не найдена\n\n"
                "Модель не существует в Replicate или недоступна.\n"
                "Проверьте настройку GENERATION_MODEL в коде бота."
            )
        elif "401" in error_detail or "unauthorized" in error_detail.lower():
            user_message = (
                "❌ Ошибка авторизации\n\n"
                "Проверьте правильность REPLICATE_API_TOKEN."
            )
        elif "429" in error_detail or "rate limit" in error_detail.lower():
            user_message = (
                "❌ Превышен лимит запросов\n\n"
                "Подождите минуту и попробуйте снова."
            )
        else:
            user_message = (
                f"❌ Ошибка: {error_detail}\n\n"
                "Попробуй ещё раз или используй /create"
            )
        
        await status_message.edit_text(user_message)
    
    return ConversationHandler.END


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    """Запуск бота"""
    
    # Проверка переменных окружения
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("❌ TELEGRAM_TOKEN not configured! Edit the file and add your token.")
        return
    
    if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
        logger.error("❌ REPLICATE_API_TOKEN not configured!")
        return
    
    # Запускаем бота
    logger.info("🚀 Bot started successfully!")
    logger.info(f"📊 Using model: {GENERATION_MODEL}")
    if USE_PREDEFINED_REFERENCE_IMAGES:
        ref_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
        logger.info(f"📸 Predefined reference images: {len(ref_images)} image(s)")
    
    # Устанавливаем токен Replicate
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Диалог создания бейджа
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("create", create_badge),
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_generate)
        ],
        states={
            WAITING_FOR_SCENE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scene_input)
            ],
            WAITING_FOR_REFERENCE_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_reference_photos),
                CommandHandler("skip", skip_reference_photos)
            ],
            WAITING_FOR_BADGE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_badge_text_input)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    
    # Регистрируем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("examples", examples_command))
    
    # Запускаем бота
    logger.info("🚀 Bot started successfully!")
    logger.info(f"📊 Using model: {GENERATION_MODEL}")
    if USE_PREDEFINED_REFERENCE_IMAGES:
        ref_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
        logger.info(f"📸 Predefined reference images: {len(ref_images)} image(s)")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
