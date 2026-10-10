# passenger_wsgi.py
# Специально для хостинга REG.RU с Python 3.7.0

import sys
import os

# Получаем путь к директории приложения
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем директорию приложения в sys.path
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Путь к виртуальному окружению на REG.RU
# Обычно создается в домашней директории пользователя
VENV_DIR = os.path.join(os.path.dirname(APP_DIR), 'myenv')  # или 'venv'

# Если виртуальное окружение существует, добавляем его пути
if os.path.exists(VENV_DIR):
    site_packages = os.path.join(VENV_DIR, 'lib', 'python3.7', 'site-packages')
    dist_packages = os.path.join(VENV_DIR, 'lib', 'python3.7', 'dist-packages')

    if os.path.exists(site_packages):
        sys.path.insert(0, site_packages)
    if os.path.exists(dist_packages):
        sys.path.insert(0, dist_packages)

# Устанавливаем переменные окружения
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['LANG'] = 'ru_RU.UTF-8'
os.environ['LC_ALL'] = 'ru_RU.UTF-8'

# Импортируем Flask-приложение
try:
    from app import app as application
except ImportError:
    # Если не удается импортировать, пробуем альтернативный путь
    sys.path.insert(0, os.path.dirname(APP_DIR))
    from app import app as application

# Локальный алиас, чтобы декораторы вида @app.before_request работали
app = application

# Настройки для production режима
application.config['ENV'] = 'production'
application.config['DEBUG'] = False

# Секретный ключ (ОБЯЗАТЕЛЬНО замените на свой!)
# Сгенерировать можно здесь: https://randomkeygen.com/
application.secret_key = 'замените-на-свой-секретный-ключ-32-символа'

# Дополнительные настройки для стабильной работы
application.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 год для кеша
application.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 часа

# Обработка кириллических URL для домена привычка-365.рф
import urllib.parse
from flask import request, redirect


@app.before_request
def handle_cyrillic_urls():
    """Обработка URL с кириллицей для IDN-домена"""
    if request.path:
        try:
            # Проверяем, есть ли в пути закодированные символы
            decoded = urllib.parse.unquote(request.path)
            if decoded != request.path and '%' in request.path:
                return redirect(decoded, code=301)
        except:
            pass


# Если есть база данных SQLite, указываем путь к ней
# Иначе файл создастся автоматически в APP_DIR
DB_PATH = os.path.join(APP_DIR, 'habit_tracker.db')
if not os.path.exists(DB_PATH):
    # Создаем файл БД с правильными правами при первом запуске
    try:
        open(DB_PATH, 'a').close()
        os.chmod(DB_PATH, 0o666)
    except:
        pass

# Логирование ошибок в файл (опционально)
import logging

LOG_FILE = os.path.join(APP_DIR, 'logs', 'flask.log')
if not os.path.exists(os.path.dirname(LOG_FILE)):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), mode=0o755)
    except:
        pass

# Настройка логгера
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
application.logger.addHandler(handler)

# Это необходимо для Passenger
# Переменная должна называться application