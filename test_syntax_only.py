#!/usr/bin/env python3
"""
Проверка синтаксиса ключевых файлов
"""

def test_syntax():
    """Проверка синтаксиса"""
    print("🔍 Проверка синтаксиса...")

    files_to_check = [
        'src/services/route_optimizer.py',
        'src/bot/handlers.py',
        'src/models/order.py',
        'src/services/maps_service.py'
    ]

    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                compile(f.read(), file_path, 'exec')
            print(f"✅ {file_path}")
        except SyntaxError as e:
            print(f"❌ {file_path}: Синтаксическая ошибка - {e}")
            return False
        except Exception as e:
            print(f"⚠️ {file_path}: {e}")

    print("✅ Синтаксис всех файлов корректен!")
    return True

if __name__ == "__main__":
    test_syntax()
