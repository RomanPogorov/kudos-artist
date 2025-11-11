"""
Скрипт для обучения LoRA модели через Replicate
Упрощённый процесс подготовки и запуска обучения
"""

import os
import zipfile
import replicate
from pathlib import Path

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

REPLICATE_API_TOKEN = "YOUR_REPLICATE_TOKEN"  # Ваш токен от replicate.com
MODEL_NAME = "samurai-badge-lora"  # Название вашей модели
TRIGGER_WORD = "aidbox_samurai_style"  # Уникальное слово-триггер

# Папка с обучающими изображениями
TRAINING_IMAGES_DIR = "./training_images"

# Параметры обучения
TRAINING_STEPS = 1000
LEARNING_RATE = 0.0004

# =============================================================================
# ФУНКЦИИ
# =============================================================================

def validate_images(images_dir: str) -> bool:
    """
    Проверяет наличие и корректность обучающих изображений
    """
    images_path = Path(images_dir)
    
    if not images_path.exists():
        print(f"❌ Папка {images_dir} не найдена!")
        print(f"Создайте папку и добавьте туда 15-25 изображений.")
        return False
    
    # Поддерживаемые форматы
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    images = [f for f in images_path.iterdir() 
              if f.is_file() and f.suffix.lower() in valid_extensions]
    
    if len(images) < 10:
        print(f"⚠️  Найдено только {len(images)} изображений.")
        print(f"Рекомендуется минимум 15 изображений для хорошего результата.")
        return False
    
    print(f"✅ Найдено {len(images)} изображений для обучения:")
    for img in sorted(images)[:5]:
        print(f"   - {img.name}")
    if len(images) > 5:
        print(f"   ... и ещё {len(images) - 5}")
    
    return True


def create_training_archive(images_dir: str, output_zip: str = "training_data.zip") -> str:
    """
    Создаёт ZIP архив с обучающими изображениями
    """
    print(f"\n📦 Создаю архив {output_zip}...")
    
    images_path = Path(images_dir)
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    images = [f for f in images_path.iterdir() 
              if f.is_file() and f.suffix.lower() in valid_extensions]
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for img in images:
            zipf.write(img, arcname=img.name)
    
    file_size = os.path.getsize(output_zip) / (1024 * 1024)  # MB
    print(f"✅ Архив создан: {output_zip} ({file_size:.1f} MB)")
    print(f"📸 Упаковано изображений: {len(images)}")
    
    return output_zip


def upload_to_replicate(zip_path: str) -> str:
    """
    Загружает архив на Replicate и возвращает URL
    
    Примечание: Replicate не предоставляет прямой upload API для обучающих данных.
    Вам нужно загрузить архив на любой файловый хостинг (Google Drive, Dropbox, etc)
    и получить прямую ссылку для скачивания.
    """
    print(f"\n⚠️  ВАЖНО: Загрузите {zip_path} на файловый хостинг")
    print(f"\nВарианты:")
    print(f"1. Google Drive:")
    print(f"   - Загрузите файл")
    print(f"   - Правый клик → Открыть доступ → Копировать ссылку")
    print(f"   - Ссылка должна быть прямой для скачивания!")
    print(f"\n2. Dropbox:")
    print(f"   - Загрузите файл")
    print(f"   - Создать ссылку → Скопировать")
    print(f"   - Замените ?dl=0 на ?dl=1 в конце URL")
    print(f"\n3. GitHub Release:")
    print(f"   - Создайте новый release в репозитории")
    print(f"   - Приложите ZIP файл")
    print(f"   - Используйте прямую ссылку на asset")
    
    zip_url = input("\n🔗 Введите прямую ссылку на архив: ").strip()
    
    if not zip_url.startswith('http'):
        print("❌ Некорректный URL!")
        return None
    
    return zip_url


def start_training(training_images_url: str) -> replicate.Training:
    """
    Запускает процесс обучения LoRA на Replicate
    """
    print(f"\n🚀 Запускаю обучение LoRA...")
    print(f"📊 Параметры:")
    print(f"   - Модель: {MODEL_NAME}")
    print(f"   - Trigger word: {TRIGGER_WORD}")
    print(f"   - Steps: {TRAINING_STEPS}")
    print(f"   - Learning rate: {LEARNING_RATE}")
    
    # Устанавливаем API токен
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    try:
        # Получаем username из API
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)
        
        # Запускаем обучение
        training = replicate.trainings.create(
            version="ostris/flux-dev-lora-trainer:4ffd32160efd92e956d39c5338a9b8fbafca58e03f791f6d8011f3e20e8ea6fa",
            input={
                "input_images": training_images_url,
                "trigger_word": TRIGGER_WORD,
                "steps": TRAINING_STEPS,
                "learning_rate": LEARNING_RATE,
            },
            destination=f"{MODEL_NAME}"  # Replicate автоматически добавит ваш username
        )
        
        print(f"\n✅ Обучение запущено!")
        print(f"📍 Training ID: {training.id}")
        print(f"🔗 URL: https://replicate.com/trainings/{training.id}")
        print(f"\n⏱  Ожидаемое время: 30-60 минут")
        print(f"💰 Примерная стоимость: $2-5")
        
        return training
        
    except Exception as e:
        print(f"❌ Ошибка при запуске обучения: {e}")
        return None


def check_training_status(training_id: str):
    """
    Проверяет статус обучения
    """
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    try:
        training = replicate.trainings.get(training_id)
        
        print(f"\n📊 Статус обучения {training_id}:")
        print(f"   Status: {training.status}")
        
        if training.status == "succeeded":
            print(f"   ✅ Обучение завершено успешно!")
            print(f"   🎯 Модель: {training.destination}")
            print(f"\n📝 Обновите badge_bot.py:")
            print(f'   LORA_MODEL = "{training.destination}"')
        elif training.status == "failed":
            print(f"   ❌ Обучение завершилось с ошибкой")
            if hasattr(training, 'error'):
                print(f"   Ошибка: {training.error}")
        elif training.status == "processing":
            print(f"   ⏳ Обучение в процессе...")
        else:
            print(f"   ℹ️  Статус: {training.status}")
        
        return training
        
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса: {e}")
        return None


# =============================================================================
# ГЛАВНОЕ МЕНЮ
# =============================================================================

def main():
    """
    Интерактивное меню для обучения LoRA
    """
    print("=" * 70)
    print("🎨 LoRA Trainer - Обучение модели для генерации бейджей")
    print("=" * 70)
    
    while True:
        print("\n📋 Выберите действие:")
        print("1. Проверить обучающие изображения")
        print("2. Создать архив для обучения")
        print("3. Запустить обучение (требуется URL архива)")
        print("4. Проверить статус обучения")
        print("5. Быстрый старт (все шаги)")
        print("0. Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "1":
            validate_images(TRAINING_IMAGES_DIR)
            
        elif choice == "2":
            if validate_images(TRAINING_IMAGES_DIR):
                zip_path = create_training_archive(TRAINING_IMAGES_DIR)
                print(f"\n✅ Архив готов: {zip_path}")
                print(f"📤 Загрузите его на файловый хостинг для следующего шага")
            
        elif choice == "3":
            if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
                print("\n❌ Установите REPLICATE_API_TOKEN в начале файла!")
                continue
                
            zip_url = input("🔗 Введите URL архива с изображениями: ").strip()
            if zip_url:
                training = start_training(zip_url)
                if training:
                    print(f"\n💾 Сохраните Training ID: {training.id}")
            
        elif choice == "4":
            training_id = input("🔍 Введите Training ID: ").strip()
            if training_id:
                check_training_status(training_id)
            
        elif choice == "5":
            print("\n🚀 Быстрый старт")
            print("=" * 70)
            
            # Шаг 1: Проверка
            if not validate_images(TRAINING_IMAGES_DIR):
                print("\n❌ Сначала подготовьте изображения!")
                continue
            
            # Шаг 2: Архив
            zip_path = create_training_archive(TRAINING_IMAGES_DIR)
            
            # Шаг 3: Загрузка
            zip_url = upload_to_replicate(zip_path)
            if not zip_url:
                continue
            
            # Шаг 4: Обучение
            if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
                print("\n❌ Установите REPLICATE_API_TOKEN в начале файла!")
                continue
            
            training = start_training(zip_url)
            if training:
                print(f"\n🎉 Всё готово! Обучение запущено.")
                print(f"💾 Training ID: {training.id}")
                print(f"\n⏭️  Следующие шаги:")
                print(f"   1. Дождитесь окончания обучения (30-60 мин)")
                print(f"   2. Проверьте статус: выберите пункт 4")
                print(f"   3. Обновите LORA_MODEL в badge_bot.py")
                print(f"   4. Запустите бота: python badge_bot.py")
            
        elif choice == "0":
            print("\n👋 До встречи!")
            break
            
        else:
            print("❌ Неверный выбор, попробуйте снова")


if __name__ == "__main__":
    main()
