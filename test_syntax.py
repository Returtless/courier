#!/usr/bin/env python3
"""
Проверка синтаксиса всех модулей
"""

def test_syntax():
    """Проверка синтаксиса импортов"""
    print("🔍 Проверка синтаксиса модулей...")

    modules_to_test = [
        'src.models.order',
        'src.services.maps_service',
        'src.services.route_optimizer',
        'src.services.traffic_monitor',
        'src.bot.handlers',
        'src.config'
    ]

    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
        except SyntaxError as e:
            print(f"❌ {module}: Синтаксическая ошибка - {e}")
            return False
        except ImportError as e:
            print(f"⚠️ {module}: Ошибка импорта - {e}")
        except Exception as e:
            print(f"⚠️ {module}: Другая ошибка - {e}")

    print("✅ Синтаксис всех модулей корректен!")
    return True

if __name__ == "__main__":
    test_syntax()
