"""
Скрипт для быстрого тестирования обученной LoRA модели
Проверяет работоспособность перед запуском бота
"""

import os
import replicate
from PIL import Image
import requests
from io import BytesIO

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

REPLICATE_API_TOKEN = "YOUR_REPLICATE_TOKEN"
LORA_MODEL = "your-username/samurai-badge-lora"
TRIGGER_WORD = "aidbox_samurai_style"

# Тестовые промпты
TEST_PROMPTS = [
    "magnifying glass",
    "katana sword",
    "laptop computer",
    "tea cup",
    "telescope",
]

# =============================================================================
# ФУНКЦИИ ТЕСТИРОВАНИЯ
# =============================================================================

def test_lora_generation(prompt: str, save_path: str = None) -> bool:
    """
    Тестирует генерацию одного изображения
    """
    try:
        print(f"\n🎨 Генерирую: {prompt}")
        
        full_prompt = f"{TRIGGER_WORD}, samurai warrior badge, character holding {prompt}, cartoon illustration, white background"
        
        output = replicate.run(
            LORA_MODEL,
            input={
                "prompt": full_prompt,
                "negative_prompt": "text, letters, words, signature, realistic",
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
            }
        )
        
        image_url = output[0] if isinstance(output, list) else output
        print(f"✅ Изображение сгенерировано: {image_url}")
        
        # Загружаем и сохраняем
        if save_path:
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content))
            img.save(save_path)
            print(f"💾 Сохранено в: {save_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def run_full_test():
    """
    Запускает полное тестирование
    """
    print("=" * 70)
    print("🧪 Тестирование LoRA модели")
    print("=" * 70)
    
    # Проверка токена
    if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
        print("\n❌ Установите REPLICATE_API_TOKEN!")
        return False
    
    if LORA_MODEL == "your-username/samurai-badge-lora":
        print("\n❌ Установите правильное имя LORA_MODEL!")
        return False
    
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    
    # Создаём папку для результатов
    os.makedirs("test_results", exist_ok=True)
    
    print(f"\n📊 Параметры:")
    print(f"   Модель: {LORA_MODEL}")
    print(f"   Trigger: {TRIGGER_WORD}")
    print(f"   Тестов: {len(TEST_PROMPTS)}")
    
    # Запускаем тесты
    results = []
    for i, prompt in enumerate(TEST_PROMPTS, 1):
        print(f"\n[{i}/{len(TEST_PROMPTS)}]", end=" ")
        save_path = f"test_results/test_{i}_{prompt.replace(' ', '_')}.png"
        success = test_lora_generation(prompt, save_path)
        results.append(success)
    
    # Итоги
    print("\n" + "=" * 70)
    print("📈 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"✅ Успешно: {success_count}/{total_count}")
    print(f"❌ Ошибок: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 Отлично! Модель работает идеально!")
        print("\n✨ Следующие шаги:")
        print("   1. Проверьте изображения в папке test_results/")
        print("   2. Если результат устраивает, обновите badge_bot.py")
        print("   3. Запустите бота: python badge_bot.py")
        return True
    elif success_count > 0:
        print("\n⚠️  Модель работает, но есть ошибки")
        print("   Проверьте конфигурацию и попробуйте снова")
        return False
    else:
        print("\n❌ Модель не работает!")
        print("\n🔍 Проверьте:")
        print("   1. Правильность имени модели (LORA_MODEL)")
        print("   2. Завершено ли обучение на Replicate")
        print("   3. Корректность API токена")
        print("   4. Баланс на аккаунте Replicate")
        return False


def interactive_test():
    """
    Интерактивное тестирование
    """
    print("=" * 70)
    print("🎨 Интерактивное тестирование LoRA")
    print("=" * 70)
    
    if REPLICATE_API_TOKEN == "YOUR_REPLICATE_TOKEN":
        print("\n❌ Сначала установите REPLICATE_API_TOKEN в начале файла!")
        return
    
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    os.makedirs("test_results", exist_ok=True)
    
    print(f"\nМодель: {LORA_MODEL}")
    print(f"Trigger: {TRIGGER_WORD}")
    print("\nВведите описание объекта (или 'quit' для выхода)")
    
    counter = 1
    while True:
        prompt = input("\n🎨 Что держит персонаж? ").strip()
        
        if prompt.lower() in ['quit', 'exit', 'q']:
            print("👋 Завершение тестирования")
            break
        
        if not prompt:
            continue
        
        save_path = f"test_results/interactive_{counter}.png"
        test_lora_generation(prompt, save_path)
        counter += 1


# =============================================================================
# ГЛАВНОЕ МЕНЮ
# =============================================================================

def main():
    print("\n📋 Выберите режим тестирования:")
    print("1. Автоматический тест (5 предустановленных промптов)")
    print("2. Интерактивный тест (вводите свои промпты)")
    print("3. Быстрая проверка (1 тест)")
    print("0. Выход")
    
    choice = input("\nВаш выбор: ").strip()
    
    if choice == "1":
        run_full_test()
    elif choice == "2":
        interactive_test()
    elif choice == "3":
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
        os.makedirs("test_results", exist_ok=True)
        test_lora_generation("magnifying glass", "test_results/quick_test.png")
    elif choice == "0":
        print("👋 До встречи!")
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
