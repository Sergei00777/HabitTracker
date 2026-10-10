import sys
import os
from app import app
import database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("===== ПОЛНЫЙ ТЕСТ СИСТЕМЫ =====")
print(f"Папка проекта: {BASE_DIR}")
print(f"Python: {sys.version}")

try:
    db.init_db(seed=True)
    db.init_tasks_db()
    print("   ✅ База данных создана и работает!")
except Exception as e:
    print(f"   ❌ Ошибка базы: {e}")

try:
    from flask import Flask

    print("   ✅ Flask импортируется!")
except Exception as e:
    print(f"   ❌ Ошибка Flask: {e}")

with app.test_client() as client:
    client.post('/login', data={'username': 'test', 'password': 'test123'})
    routes = [
        ("/", 200),
        ("/daily/2026/9", 200),
        ("/weekly/2026/9", 200),
        ("/monthly/2026/9", 200),
        ("/goals", 200),
        ("/tasks", 200),
        ("/tasks/kanban", 200),
        ("/tasks/matrix", 200),
        ("/tasks/calendar/2026/9", 200),
        ("/tasks/planner/daily", 200),
        ("/tasks/planner/weekly", 200),
    ]

    for r, expected in routes:
        resp = client.get(r)
        status = resp.status_code
        if status == expected:
            print(f"   ✅ {r} — {status}")
        elif status == 404:
            print(f"   ❌ {r} — {status} (маршрут не найден)")
        elif status == 500:
            print(f"   ❌ {r} — {status} (ошибка сервера)")
        else:
            print(f"   ⚠️ {r} — {status}")

with app.test_client() as client:
    client.post('/login', data={'username': 'test', 'password': 'test123'})
    print("\n   Тест 4.1: Ежедневный тоггл")
    resp = client.post('/daily/toggle', json={'habit_id': 1, 'year': 2026, 'month': 9, 'day': 1})
    if resp.status_code == 200:
        print(f"   ✅ Статус: {resp.status_code}, Ответ: {resp.get_json()}")
    else:
        print(f"   ❌ Статус: {resp.status_code}")

    print("\n   Тест 4.2: Еженедельный тоггл")
    resp = client.post('/weekly/toggle', json={'habit_id': 1, 'year': 2026, 'month': 9, 'week': 1})
    if resp.status_code == 200:
        print(f"   ✅ Статус: {resp.status_code}")
    else:
        print(f"   ❌ Статус: {resp.status_code}")

    print("\n   Тест 4.3: Ежемесячный тоггл")
    resp = client.post('/monthly/toggle', json={'habit_id': 1, 'year': 2026, 'month': 9})
    if resp.status_code == 200:
        print(f"   ✅ Статус: {resp.status_code}")
    else:
        print(f"   ❌ Статус: {resp.status_code}")

    print("\n   Тест 4.4: Тоггл шага цели")
    resp = client.post('/goals/step/toggle', json={'step_id': 1})
    if resp.status_code == 200:
        print(f"   ✅ Статус: {resp.status_code}")
    else:
        print(f"   ❌ Статус: {resp.status_code}")

print("\n===== ТЕСТ ЗАВЕРШЕН =====")