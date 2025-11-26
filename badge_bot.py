"""
Telegram Bot для автоматической генерации бейджей с Nonabana
Пользователь пишет текст → бот генерирует картинку с использованием reference images
"""

import os
import logging
import requests
import tempfile
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import replicate
from replicate.exceptions import ReplicateError
from deep_translator import GoogleTranslator
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
# КОНФИГУРАЦИЯ
# =============================================================================

# API Токены
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "YOUR_REPLICATE_TOKEN")

# Модели Replicate
GENERATION_MODEL = "google/nano-banana"
GENERATION_SEED = None  # None = случайный, число = фиксированный seed
BACKGROUND_REMOVAL_MODEL = "851-labs/background-remover:a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
BACKGROUND_REMOVAL_ENABLED = False  # Активировано

# Режим генерации текста
GENERATE_TEXT_IN_PROMPT = True  # True = текст генерируется в промпте, False = добавляется программно

# Референсные изображения
REFERENCE_IMAGES_DIR = "reference_images"
USE_PREDEFINED_REFERENCE_IMAGES = True
FEMALE_REFERENCE_IMAGE = "Girl.jpg"  # Референс для женских персонажей

# Ключевые слова для определения женского персонажа
FEMALE_KEYWORDS = [
    'girl', 'woman', 'female', 'lady', 'she', 'her', 'wife', 'mother', 'mom', 'daughter',
    'девушка', 'женщина', 'девочка', 'дама', 'жена', 'мать', 'мама', 'дочь', 'дочка',
    'сестра', 'sister', 'бабушка', 'grandmother', 'тётя', 'aunt'
]

# Настройки текста на бейдже
FONT_PATH = "fonts/Golos-Text_Bold.ttf"
FONT_SIZE_BASE = 80
FONT_SIZE_MIN = 60
FONT_SIZE_MAX = 100
TEXT_COLOR = "#000000"
TEXT_BEND_SHORT = 20  # Изгиб для текста <= 12 символов
TEXT_BEND_LONG = 28   # Изгиб для текста > 12 символов
TEXT_VERTICAL_OFFSET = 6  # Смещение текста вверх (пиксели)
TEXT_LETTER_SPACING = 0.02  # Разрядка между буквами
TEXT_MAX_LENGTH = 20  # Максимальная длина текста на баннере

# Настройки поиска баннера
BANNER_SEARCH_AREA_START = 0.6  # Начинаем поиск с 60% высоты изображения
BANNER_DEFAULT_Y_POSITION = 0.93  # Позиция по умолчанию (93% от высоты)
BANNER_YELLOW_LOWER = [200, 160, 40]   # RGB нижняя граница жёлтого
BANNER_YELLOW_UPPER = [255, 220, 100]  # RGB верхняя граница жёлтого

# Текстовые сообщения
MESSAGES = {
    "start": """👋 Привет, {name}!

Я создаю бейджи с самураем в твоём уникальном стиле.

🎨 **Как это работает:**
1. Опиши коротко что должно быть с самураем
   Например: "с гитарой, с клавиатурой, в боевой стойке с мечом, с молотком, в овечьей шкуре"
2. Укажи текст для баннера на бейдже, не более 12 символов
   Например: "DEBUG NINJA", "CODE MASTER"
3. Получи готовый бейдж!

Просто напиши мне что-нибудь, и начнём! 🚀

Команды:
/create - Создать новый бейдж
/help - Помощь
/examples - Примеры запросов""",

    "help": """📖 **Справка по использованию**

Опиши коротко что должно быть с самураем
• Например: "с гитарой, с клавиатурой, в боевой стойке с мечом, с молотком, в овечьей шкуре"
• Можно на русском или английском
• Опиши что должно быть на картинке

Укажи текст для баннера
• До {max_length} символов для лучшего вида
• Английские заглавные буквы смотрятся лучше
• Примеры: "UX SCOUT", "DEBUG NINJA"

⏱ Генерация занимает 10-30 секунд

💡 Если результат не понравился, просто начните заново!""",

    "examples": """💡 **Примеры хороших запросов:**

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
- Длинные тексты: "THE BEST DEVELOPER IN THE WORLD\"""",

    "cancel": "❌ Создание бейджа отменено.\nИспользуй /create чтобы начать заново!",

    "create_start": """🎨 Создаём новый бейдж!

Опиши коротко что должно быть с самураем
Например: "с гитарой, с клавиатурой, в боевой стойке с мечом, с молотком, в овечьей шкуре"

Или /cancel для отмены""",

    "scene_received": """✅ Отлично! Сюжет: *{scene}*

📸 Использую предустановленные референсные фото ({count} шт.)

Какой текст написать на баннере?
Например: DEBUG NINJA, CODE MASTER, UX SCOUT...

(До {max_length} символов)""",

    "scene_received_no_refs": """✅ Отлично! Сюжет: *{scene}*

⚠️ Референсные фото не найдены в папке {ref_dir}

Какой текст написать на баннере?
Например: DEBUG NINJA, CODE MASTER, UX SCOUT...

(До {max_length} символов)""",

    "scene_received_old_mode": """✅ Отлично! Сюжет: *{scene}*

Хочешь добавить референсные фото? (опционально)
Отправь фото или напиши /skip чтобы пропустить

Можно отправить до 4 фото""",

    "photo_uploaded_max": """✅ Загружено {count} фото (максимум)

Какой текст написать на баннере?
Например: DEBUG NINJA, CODE MASTER, UX SCOUT...

(До {max_length} символов)""",

    "photo_uploaded": """✅ Фото {count}/4 загружено

Отправь ещё фото или напиши /skip чтобы перейти к тексту баннера""",

    "photo_error": "❌ Пожалуйста, отправь фото или используй /skip",

    "skip_photos": """⏭ Пропускаем референсные фото

Какой текст написать на баннере?
Например: DEBUG NINJA, CODE MASTER, UX SCOUT...

(До {max_length} символов)""",

    "text_too_long": """⚠️ Текст слишком длинный (максимум {max_length} символов).
Попробуй покороче:""",

    "generating": "⏳ Создаю твой бейдж...\nЭто займёт 10-30 секунд ⚡",
    "generating_quick": "⏳ Создаю бейдж...",

    "badge_ready": """🎊 Твой бейдж готов!

🎨 Сюжет: {scene}
📝 Текст: {text}

Хочешь ещё? Просто напиши /create""",

    "badge_ready_quick": "🎊 Готово!\n{scene} | {text}",

    "errors": {
        "model_not_found": """❌ Модель не найдена

Модель не существует в Replicate или недоступна.
Проверьте настройку GENERATION_MODEL в коде бота.""",

        "auth_error": """❌ Ошибка авторизации

Проверьте правильность REPLICATE_API_TOKEN.""",

        "rate_limit": """❌ Превышен лимит запросов

Подождите минуту и попробуйте снова.""",

        "generic": """❌ Ошибка при создании бейджа.
Попробуй ещё раз через /create

Если ошибка повторяется, попробуй:
• Упростить описание объекта
• Использовать другой текст
• Подождать минуту и попробовать снова""",

        "generic_quick": "❌ Ошибка: {detail}\n\nПопробуй ещё раз или используй /create"
    }
}

# Состояния диалога
WAITING_FOR_SCENE, WAITING_FOR_BADGE_TEXT, WAITING_FOR_REFERENCE_PHOTOS = range(3)

# =============================================================================
# ФУНКЦИИ ГЕНЕРАЦИИ
# =============================================================================

def find_yellow_banner_center(img: Image.Image, user_id: int) -> tuple:
    """Находит центр жёлтого баннера на изображении по цвету"""
    try:
        img_array = np.array(img)
        height = img_array.shape[0]
        width = img_array.shape[1]
        search_area = img_array[int(height * BANNER_SEARCH_AREA_START):, :]
        
        if search_area.shape[-1] == 4:
            search_area = search_area[:, :, :3]
        
        lower_yellow = np.array(BANNER_YELLOW_LOWER)
        upper_yellow = np.array(BANNER_YELLOW_UPPER)
        mask = np.all((search_area >= lower_yellow) & (search_area <= upper_yellow), axis=-1)
        yellow_pixels = np.where(mask)
        
        if len(yellow_pixels[0]) > 0:
            center_y = int(np.mean(yellow_pixels[0])) + int(height * BANNER_SEARCH_AREA_START)
            center_x = int(np.mean(yellow_pixels[1]))
            logger.info(f"User {user_id}: Found yellow banner at ({center_x}, {center_y})")
            return (center_x, center_y)
        else:
            logger.warning(f"User {user_id}: Yellow banner not found, using default position")
            return (width // 2, int(height * BANNER_DEFAULT_Y_POSITION))
    except Exception as e:
        logger.error(f"User {user_id}: Error finding yellow banner: {e}")
        return (img.width // 2, int(img.height * BANNER_DEFAULT_Y_POSITION))


def is_female_prompt(text: str) -> bool:
    """Проверяет, содержит ли текст упоминание женского персонажа"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in FEMALE_KEYWORDS)


# Ключевые слова для определения активной/динамичной сцены
ACTION_KEYWORDS = [
    'fight', 'fighting', 'battle', 'attack', 'sword', 'katana', 'strike', 'slash', 'jump', 'run',
    'бой', 'битва', 'атака', 'меч', 'катана', 'удар', 'прыжок', 'бежать', 'сражение', 'рубит',
    'combat', 'warrior', 'action', 'dynamic', 'stance', 'боевой', 'стойка', 'воин'
]


def is_action_scene(text: str) -> bool:
    """Проверяет, является ли сцена активной/динамичной"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ACTION_KEYWORDS)


def load_single_reference_image(filename: str) -> list:
    """Загружает один конкретный референсный файл"""
    filepath = os.path.join(REFERENCE_IMAGES_DIR, filename)
    if not os.path.exists(filepath):
        logger.warning(f"Reference image {filepath} does not exist")
        return []
    
    try:
        with open(filepath, 'rb') as f:
            img_bytes = BytesIO(f.read())
            img_bytes.seek(0)
            logger.info(f"Loaded single reference image: {filename}")
            return [img_bytes]
    except Exception as e:
        logger.warning(f"Failed to load {filename}: {e}")
        return []


def load_reference_images_for_prompt(prompt: str) -> list:
    """Загружает референсы в зависимости от содержимого промпта"""
    if is_female_prompt(prompt):
        logger.info(f"Detected female character in prompt, using {FEMALE_REFERENCE_IMAGE}")
        return load_single_reference_image(FEMALE_REFERENCE_IMAGE)
    else:
        return load_reference_images_from_dir(REFERENCE_IMAGES_DIR)


def load_reference_images_from_dir(directory: str) -> list:
    """Загружает референсные фото из указанной папки, исключая специальные референсы"""
    reference_images = []
    
    if not os.path.exists(directory):
        logger.warning(f"Directory {directory} does not exist")
        return reference_images
    
    supported_formats = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    excluded_files = [FEMALE_REFERENCE_IMAGE.lower()]
    
    try:
        files = [f for f in os.listdir(directory) 
                if os.path.isfile(os.path.join(directory, f)) 
                and f.lower().endswith(supported_formats)
                and f.lower() not in excluded_files]
        files.sort()
        
        for filename in files:
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'rb') as f:
                    img_bytes = BytesIO(f.read())
                    img_bytes.seek(0)
                    reference_images.append(img_bytes)
                    logger.info(f"Loaded reference image: {filename}")
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        
        logger.info(f"Loaded {len(reference_images)} reference image(s) from {directory}")
    except Exception as e:
        logger.error(f"Error loading reference images: {e}")
    
    return reference_images


def translate_to_english(text: str, user_id: int) -> str:
    """Переводит текст с русского на английский"""
    try:
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
        if has_cyrillic:
            logger.info(f"User {user_id}: Translating '{text}' from Russian to English")
            translator = GoogleTranslator(source='ru', target='en')
            translated = translator.translate(text)
            logger.info(f"User {user_id}: Translated to '{translated}'")
            return translated
        return text
    except Exception as e:
        logger.warning(f"User {user_id}: Translation failed: {e}")
        return text


def generate_image_with_lora(scene_description: str, user_id: int, reference_images: list = None, badge_text: str = None) -> str:
    """Генерирует изображение через модель google/nano-banana"""
    if not os.getenv("REPLICATE_API_TOKEN"):
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    try:
        logger.info(f"User {user_id}: Generating image with scene '{scene_description}'")
        
        # Определяем тип сцены
        is_action = is_action_scene(scene_description)
        pose_prompt = "standing dynamic pose, waist-up shot" if is_action else "sitting in lotus pose, calm meditative"
        logger.info(f"User {user_id}: Scene type: {'action' if is_action else 'calm'}")
        
        # Определяем пол персонажа
        is_female = is_female_prompt(scene_description)
        gender_prompt = "female samurai woman" if is_female else "male samurai man"
        
        # Формируем базовый промпт
        prompt_parts = [
            f"single {gender_prompt}",
            pose_prompt,
            "upper body only",
            scene_description,
            "anatomically correct two hands only",
            "if holding sword then single katana held with both hands",
            "large red circle behind the character with white diagonal scratch marks across it",
            "red sun with white claw scratches",
            "plain light grey background",
            "isolated character",
            "centered composition",
            "solo character",
            "Japanese samurai style",
            "clean minimal background",
            "vector art style",
            "flat illustration"
        ]
        
        # Если включена генерация текста в промпте и текст передан
        if GENERATE_TEXT_IN_PROMPT and badge_text:
            badge_text_upper = badge_text.upper()
            prompt_parts.append(f"bold black text '{badge_text_upper}' at the bottom, no background behind text")
            logger.info(f"User {user_id}: Including badge text '{badge_text_upper}' in prompt")
        else:
            prompt_parts.append("space for text at the bottom")
        
        prompt = ", ".join(prompt_parts)
        
        # Негативный промпт с учётом пола
        negative_gender = "male, man, masculine" if is_female else "female, woman, feminine, girl"
        
        nano_banana_input = {
            "prompt": prompt,
            "negative_prompt": f"{negative_gender}, multiple people, crowd, full body, legs visible, standing full figure, background scenery, landscape, buildings, complex background, group photo, many characters, detailed background, other people, extras, text errors, misspelled words, wrong text, realistic photo, 3d render, yellow banner, text banner, text background, ribbon, badge, label behind text, colored background behind text, extra hands, extra arms, three hands, four hands, multiple hands, deformed hands, mutated hands, extra fingers, missing fingers, fused fingers, bad anatomy, multiple swords, two swords, dual wield, extra weapons, sword on back",
            "output_format": "jpg",
        }
        
        if reference_images:
            image_inputs = []
            for ref_image in reference_images:
                if isinstance(ref_image, BytesIO):
                    ref_image.seek(0)
                    image_inputs.append(ref_image)
                else:
                    image_inputs.append(ref_image)
            
            if image_inputs:
                nano_banana_input["image_input"] = image_inputs
                nano_banana_input["aspect_ratio"] = "match_input_image"
                logger.info(f"User {user_id}: Added {len(image_inputs)} reference image(s)")
        
        if GENERATION_SEED is not None:
            nano_banana_input["seed"] = int(GENERATION_SEED)
        
        output = replicate.run(GENERATION_MODEL, input=nano_banana_input)
        
        if hasattr(output, 'url'):
            image_url = output.url()
        else:
            image_url = output[0] if isinstance(output, list) else output
        
        logger.info(f"User {user_id}: Image generated successfully")
        return image_url
        
    except ReplicateError as e:
        error_detail = str(e)
        logger.error(f"User {user_id}: ReplicateError: {error_detail}")
        
        if "404" in error_detail or "not found" in error_detail.lower():
            error_msg = (
                f"❌ Модель не найдена (404)\n\n"
                f"Модель '{GENERATION_MODEL}' не существует в Replicate.\n\n"
                f"Проверьте модель на: https://replicate.com/{GENERATION_MODEL.split(':')[0]}"
            )
        else:
            error_msg = f"❌ Ошибка Replicate API: {error_detail}"
        
        raise ValueError(error_msg) from e
    except Exception as e:
        logger.error(f"User {user_id}: Error generating image: {e}")
        raise


def remove_background(image_bytes: BytesIO, user_id: int) -> BytesIO:
    """Удаляет фон с изображения через Replicate API"""
    if not BACKGROUND_REMOVAL_ENABLED:
        image_bytes.seek(0)
        return image_bytes
    
    try:
        logger.info(f"User {user_id}: Removing background")
        
        if not os.getenv("REPLICATE_API_TOKEN"):
            os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
        
        image_bytes.seek(0)
        img = Image.open(image_bytes)
        
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            img.save(temp_file, format='PNG', quality=95)
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as img_file:
                output = replicate.run(
                    BACKGROUND_REMOVAL_MODEL,
                    input={
                        "image": img_file,
                        "format": "png",
                        "reverse": False,
                        "threshold": 0,
                        "background_type": "rgba"
                    }
                )
            
            if hasattr(output, 'read'):
                result_bytes = BytesIO(output.read())
                result_bytes.seek(0)
                return result_bytes
            elif hasattr(output, 'url'):
                image_url = output.url()
                response = requests.get(image_url)
                response.raise_for_status()
                result_bytes = BytesIO(response.content)
                result_bytes.seek(0)
                return result_bytes
            elif isinstance(output, (list, tuple)) and len(output) > 0:
                image_url = output[0]
                response = requests.get(image_url)
                response.raise_for_status()
                result_bytes = BytesIO(response.content)
                result_bytes.seek(0)
                return result_bytes
            else:
                image_url = str(output)
                if image_url.startswith('http'):
                    response = requests.get(image_url)
                    response.raise_for_status()
                    result_bytes = BytesIO(response.content)
                    result_bytes.seek(0)
                    return result_bytes
                raise ValueError(f"Unexpected output format: {type(output)}")
        finally:
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"User {user_id}: Failed to delete temp file: {e}")
    except Exception as e:
        logger.error(f"User {user_id}: Error removing background: {e}")
        image_bytes.seek(0)
        return image_bytes


def add_text_to_badge(image_url: str, badge_text: str, user_id: int) -> BytesIO:
    """Добавляет текст на баннер бейджа"""
    try:
        logger.info(f"User {user_id}: Adding text '{badge_text}' to badge")
        
        response = requests.get(image_url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.convert('RGBA')
        
        draw = ImageDraw.Draw(img)
        badge_text = badge_text.upper()
        
        image_width = img.width
        scale_factor = image_width / 1024
        font_size = int(FONT_SIZE_BASE * scale_factor)
        font_size = max(FONT_SIZE_MIN, min(font_size, FONT_SIZE_MAX))
        
        font = None
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except Exception:
                font = ImageFont.load_default()
        
        if font is None:
            raise ValueError("Failed to load any font")
        
        banner_center_x, banner_center_y = find_yellow_banner_center(img, user_id)
        
        bend_amount = TEXT_BEND_SHORT if len(badge_text) <= 12 else TEXT_BEND_LONG
        
        char_widths = []
        total_width = 0
        for char in badge_text:
            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_width = char_bbox[2] - char_bbox[0]
            char_widths.append(char_width)
            total_width += char_width * (1 + TEXT_LETTER_SPACING)
        
        total_width -= char_widths[-1] * TEXT_LETTER_SPACING
        start_x = banner_center_x - total_width / 2
        
        current_x = start_x
        for i, char in enumerate(badge_text):
            char_width = char_widths[i]
            relative_pos = (current_x + char_width/2 - banner_center_x) / (total_width / 2)
            y_offset = bend_amount * (relative_pos ** 2)
            
            draw.text(
                (current_x, banner_center_y - y_offset - TEXT_VERTICAL_OFFSET),
                char,
                font=font,
                fill=TEXT_COLOR,
                anchor="lt"
            )
            
            current_x += char_width * (1 + TEXT_LETTER_SPACING)
        
        output = BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)
        
        logger.info(f"User {user_id}: Badge completed successfully")
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
    await update.message.reply_text(MESSAGES["start"].format(name=user.first_name))
    return WAITING_FOR_SCENE


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(MESSAGES["help"].format(max_length=TEXT_MAX_LENGTH))


async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /examples"""
    await update.message.reply_text(MESSAGES["examples"])


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    await update.message.reply_text(MESSAGES["cancel"])
    context.user_data.clear()
    return ConversationHandler.END


async def create_badge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания бейджа"""
    await update.message.reply_text(MESSAGES["create_start"])
    return WAITING_FOR_SCENE


async def handle_scene_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания сюжета"""
    user_id = update.effective_user.id
    scene_description = update.message.text.strip()
    scene_description_en = translate_to_english(scene_description, user_id)
    
    context.user_data['scene'] = scene_description_en
    context.user_data['scene_original'] = scene_description
    
    display_text = scene_description if scene_description == scene_description_en else f"{scene_description} ({scene_description_en})"
    
    if USE_PREDEFINED_REFERENCE_IMAGES:
        reference_images = load_reference_images_for_prompt(scene_description_en)
        context.user_data['reference_images'] = reference_images
        
        if reference_images:
            await update.message.reply_text(
                MESSAGES["scene_received"].format(
                    scene=display_text,
                    count=len(reference_images),
                    max_length=TEXT_MAX_LENGTH
                ),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                MESSAGES["scene_received_no_refs"].format(
                    scene=display_text,
                    ref_dir=REFERENCE_IMAGES_DIR,
                    max_length=TEXT_MAX_LENGTH
                ),
                parse_mode='Markdown'
            )
        return WAITING_FOR_BADGE_TEXT
    else:
        await update.message.reply_text(
            MESSAGES["scene_received_old_mode"].format(scene=display_text),
            parse_mode='Markdown'
        )
        context.user_data['reference_images'] = []
        return WAITING_FOR_REFERENCE_PHOTOS


async def handle_reference_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки референсных фото"""
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        photo_bytes = BytesIO()
        await file.download_to_memory(photo_bytes)
        photo_bytes.seek(0)
        
        if 'reference_images' not in context.user_data:
            context.user_data['reference_images'] = []
        
        context.user_data['reference_images'].append(photo_bytes)
        count = len(context.user_data['reference_images'])
        
        if count >= 4:
            await update.message.reply_text(
                MESSAGES["photo_uploaded_max"].format(count=count, max_length=TEXT_MAX_LENGTH),
                parse_mode='Markdown'
            )
            return WAITING_FOR_BADGE_TEXT
        else:
            await update.message.reply_text(MESSAGES["photo_uploaded"].format(count=count))
            return WAITING_FOR_REFERENCE_PHOTOS
    else:
        await update.message.reply_text(MESSAGES["photo_error"])
        return WAITING_FOR_REFERENCE_PHOTOS


async def skip_reference_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск загрузки референсных фото"""
    await update.message.reply_text(
        MESSAGES["skip_photos"].format(max_length=TEXT_MAX_LENGTH),
        parse_mode='Markdown'
    )
    return WAITING_FOR_BADGE_TEXT


async def handle_badge_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для баннера и генерация финального бейджа"""
    user_id = update.effective_user.id
    badge_text = update.message.text.strip()
    
    if len(badge_text) > TEXT_MAX_LENGTH:
        await update.message.reply_text(
            MESSAGES["text_too_long"].format(max_length=TEXT_MAX_LENGTH)
        )
        return WAITING_FOR_BADGE_TEXT
    
    scene_description = context.user_data.get('scene', 'unknown scene')
    reference_images = context.user_data.get('reference_images', [])
    
    status_message = await update.message.reply_text(MESSAGES["generating"])
    
    try:
        # Передаём текст в генерацию, если включен режим генерации текста в промпте
        image_url = generate_image_with_lora(
            scene_description, 
            user_id, 
            reference_images,
            badge_text=badge_text if GENERATE_TEXT_IN_PROMPT else None
        )
        
        # Если текст генерируется в промпте, пропускаем этап добавления текста
        if GENERATE_TEXT_IN_PROMPT:
            # Загружаем изображение напрямую
            response = requests.get(image_url)
            response.raise_for_status()
            image_with_text = BytesIO(response.content)
            image_with_text.seek(0)
        else:
            image_with_text = add_text_to_badge(image_url, badge_text, user_id)
        
        if BACKGROUND_REMOVAL_ENABLED:
            image_with_text = remove_background(image_with_text, user_id)
        
        await status_message.delete()
        
        original_scene = context.user_data.get('scene_original', scene_description)
        caption = MESSAGES["badge_ready"].format(scene=original_scene, text=badge_text)
        
        await update.message.reply_photo(photo=image_with_text, caption=caption)
        logger.info(f"User {user_id}: Badge created successfully")
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"User {user_id}: Configuration error: {error_msg}")
        await status_message.edit_text(error_msg)
    except Exception as e:
        logger.error(f"User {user_id}: Failed to create badge: {e}")
        error_detail = str(e)
        
        if "404" in error_detail or "not found" in error_detail.lower():
            user_message = MESSAGES["errors"]["model_not_found"]
        elif "401" in error_detail or "unauthorized" in error_detail.lower():
            user_message = MESSAGES["errors"]["auth_error"]
        elif "429" in error_detail or "rate limit" in error_detail.lower():
            user_message = MESSAGES["errors"]["rate_limit"]
        else:
            user_message = MESSAGES["errors"]["generic"]
        
        await status_message.edit_text(user_message)
    
    context.user_data.clear()
    return ConversationHandler.END


async def handle_quick_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрая генерация в одно сообщение"""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    if '|' in message_text:
        parts = message_text.split('|')
        scene_description = parts[0].strip()
        badge_text = parts[1].strip() if len(parts) > 1 else "SAMURAI"
        scene_description_en = translate_to_english(scene_description, user_id)
    else:
        scene_description_en = translate_to_english(message_text, user_id)
        context.user_data['scene'] = scene_description_en
        context.user_data['scene_original'] = message_text
        
        display_text = message_text if message_text == scene_description_en else f"{message_text} ({scene_description_en})"
        
        if USE_PREDEFINED_REFERENCE_IMAGES:
            reference_images = load_reference_images_for_prompt(scene_description_en)
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
    
    status_message = await update.message.reply_text(MESSAGES["generating_quick"])
    
    reference_images = []
    if USE_PREDEFINED_REFERENCE_IMAGES:
        reference_images = load_reference_images_for_prompt(scene_description_en)
    
    try:
        # Передаём текст в генерацию, если включен режим генерации текста в промпте
        image_url = generate_image_with_lora(
            scene_description_en, 
            user_id, 
            reference_images,
            badge_text=badge_text if GENERATE_TEXT_IN_PROMPT else None
        )
        
        # Если текст генерируется в промпте, пропускаем этап добавления текста
        if GENERATE_TEXT_IN_PROMPT:
            # Загружаем изображение напрямую
            response = requests.get(image_url)
            response.raise_for_status()
            image_with_text = BytesIO(response.content)
            image_with_text.seek(0)
        else:
            image_with_text = add_text_to_badge(image_url, badge_text, user_id)
        
        if BACKGROUND_REMOVAL_ENABLED:
            image_with_text = remove_background(image_with_text, user_id)
        
        await status_message.delete()
        original_scene = context.user_data.get('scene_original', scene_description_en)
        await update.message.reply_photo(
            photo=image_with_text,
            caption=MESSAGES["badge_ready_quick"].format(scene=original_scene, text=badge_text)
        )
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"User {user_id}: Configuration error: {error_msg}")
        await status_message.edit_text(error_msg)
    except Exception as e:
        logger.error(f"User {user_id}: Failed to create badge: {e}")
        error_detail = str(e)
        
        if "404" in error_detail or "not found" in error_detail.lower():
            user_message = MESSAGES["errors"]["model_not_found"]
        elif "401" in error_detail or "unauthorized" in error_detail.lower():
            user_message = MESSAGES["errors"]["auth_error"]
        elif "429" in error_detail or "rate limit" in error_detail.lower():
            user_message = MESSAGES["errors"]["rate_limit"]
        else:
            user_message = MESSAGES["errors"]["generic_quick"].format(detail=error_detail)
        
        await status_message.edit_text(user_message)
    
    return ConversationHandler.END


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    """Запуск бота"""
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("❌ TELEGRAM_TOKEN not configured!")
        return
    
    if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
        logger.error("❌ REPLICATE_API_TOKEN not configured!")
        return
    
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    logger.info("🚀 Bot started successfully!")
    logger.info(f"📊 Using model: {GENERATION_MODEL}")
    
    if USE_PREDEFINED_REFERENCE_IMAGES:
        ref_images = load_reference_images_from_dir(REFERENCE_IMAGES_DIR)
        logger.info(f"📸 Predefined reference images: {len(ref_images)} image(s)")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
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
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("examples", examples_command))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
