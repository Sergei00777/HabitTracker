import sys
import os

# Путь к проекту
BASE_DIR = '/var/www/u3303458/data/www/привычка-365.рф'
sys.path.insert(0, BASE_DIR)

# 1. Проверяем базу данных
print("=== Проверка базы данных ===")
try:
    import database as db

    db.init_db(seed=True)
    db.init_tasks_db()
    print("✅ База данных создана/обновлена успешно!")
except Exception as e:
    print(f"❌ Ошибка базы данных: {e}")

# 2. Проверяем, что Flask работает
print("\n=== Проверка Flask ===")
try:
    from app import app

    print("✅ Flask-приложение импортируется успешно!")
except Exception as e:
    print(f"❌ Ошибка импорта Flask: {e}")

# 3. Проверяем все маршруты приложения
print("\n=== Проверка маршрутов ===")
try:
    with app.test_client() as client:
        routes = [
            ("/", 302),  # Главная перенаправляет на daily
            ("/daily/2026/9", 200),  # Ежедневные
            ("/weekly/2026/9", 200),  # Еженедельные
            ("/monthly/2026/9", 200),  # Ежемесячные
            ("/goals", 200),  # Трекер целей
            ("/tasks", 200),  # Трекер задач
            ("/tasks/kanban", 200),  # Канбан
            ("/tasks/matrix", 200),  # Матрица
            ("/tasks/calendar/2026/9", 200),  # Календарь
            ("/tasks/planner/daily", 200),  # Дневной планер
            ("/tasks/planner/weekly", 200),  # Недельный планер
        ]

        for route, expected in routes:
            response = client.get(route)
            status = response.status_code
            if status == expected:
                print(f"✅ {route} — статус {status} (ожидалось {expected})")
            elif status == 404:
                print(f"❌ {route} — статус {status}. Ошибка: Маршрут не найдена. Проблема в шаблоне или базе.")
            elif status == 403:
                print(f"❌ {route} — статус {status}. Ошибка: Доступ запрещен. Проблема в Apache.")
            else:
                print(f"⚠️ {route} — статус {status} (ожидалось {expected})")
except Exception as e:
    print(f"❌ Ошибка при проверке маршрутов: {e}")

# 4. Проверяем виртуальное окружение
print("\n=== Проверка окружения ===")
print(f"Python: {sys.version}")
print(f"Активированное окружение: {'venv' if 'venv' in sys.prefix else 'НЕ активировано'}")