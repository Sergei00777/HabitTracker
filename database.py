"""
Слой работы с БД для Трекера Привычек.
Добавлена админ-панель и логирование посещений.
"""
import sqlite3
import calendar
from datetime import date, datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habit_tracker.db")

MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

STATUSES = ["Не начато", "В процессе", "Выполнено", "В ожидании", "Приостановлено"]
PRIORITIES = ["Критичный", "Высокий", "Средний", "Низкий"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=True):
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS daily_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        goal INTEGER,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS weekly_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS monthly_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS daily_entries (
        habit_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        done INTEGER DEFAULT 0,
        PRIMARY KEY (habit_id, year, month, day),
        FOREIGN KEY (habit_id) REFERENCES daily_habits(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS weekly_entries (
        habit_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        week INTEGER NOT NULL,
        done INTEGER DEFAULT 0,
        PRIMARY KEY (habit_id, year, month, week),
        FOREIGN KEY (habit_id) REFERENCES weekly_habits(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS monthly_entries (
        habit_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        done INTEGER DEFAULT 0,
        PRIMARY KEY (habit_id, year, month),
        FOREIGN KEY (habit_id) REFERENCES monthly_habits(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        sphere TEXT,
        reward TEXT,
        deadline TEXT,
        status TEXT DEFAULT 'in_progress',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS goal_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        done INTEGER DEFAULT 0,
        FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        due_date TEXT,
        assignee TEXT,
        status TEXT DEFAULT 'Не начато',
        category TEXT,
        priority TEXT DEFAULT 'Средний',
        important INTEGER DEFAULT 0,
        urgent INTEGER DEFAULT 0,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        task_id INTEGER,
        note TEXT,
        UNIQUE(user_id, date, time),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ip TEXT,
        user_agent TEXT,
        path TEXT,
        visited_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)
    conn.commit()

    if seed:
        import hashlib

        # Проверяем, есть ли пользователь admin
        cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cur.fetchone()[0] == 0:
            password_hash = hashlib.sha256("336996ZZz!".encode()).hexdigest()
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                ("admin", "Администратор", password_hash, 1)
            )
            user_id = cur.lastrowid

            # Добавляем тестовые привычки для админа
            cur.execute("INSERT INTO daily_habits (user_id, name, goal) VALUES (?, 'Пить воду', 30)", (user_id,))
            cur.execute("INSERT INTO daily_habits (user_id, name, goal) VALUES (?, 'Читать 20 минут', 20)", (user_id,))
            cur.execute("INSERT INTO daily_habits (user_id, name, goal) VALUES (?, 'Зарядка', 25)", (user_id,))

            cur.execute("INSERT INTO weekly_habits (user_id, name) VALUES (?, 'Ходить в зал 2 раза')", (user_id,))
            cur.execute("INSERT INTO weekly_habits (user_id, name) VALUES (?, 'Убираться дома')", (user_id,))

            cur.execute("INSERT INTO monthly_habits (user_id, name) VALUES (?, 'Читать 1 книгу')", (user_id,))
            cur.execute("INSERT INTO monthly_habits (user_id, name) VALUES (?, 'Смотреть 1 фильм')", (user_id,))

            cur.execute("""
                INSERT INTO tasks (user_id, title, due_date, assignee, status, category, priority)
                VALUES (?, 'Проект', '2026-09-15', 'Иван', 'В процессе', 'Работа', 'Высокий')
            """, (user_id,))
            cur.execute("""
                INSERT INTO tasks (user_id, title, due_date, assignee, status, category, priority)
                VALUES (?, 'Покупка продуктов', '2026-09-02', 'Анна', 'Не начато', 'Дом', 'Средний')
            """, (user_id,))

        # Проверяем, есть ли тестовый пользователь test
        cur.execute("SELECT COUNT(*) FROM users WHERE username = 'test'")
        if cur.fetchone()[0] == 0:
            password_hash = hashlib.sha256("test123".encode()).hexdigest()
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                ("test", "Тестовый Пользователь", password_hash, 0)
            )
            test_id = cur.lastrowid

            # Добавляем тестовые привычки
            cur.execute("INSERT INTO daily_habits (user_id, name, goal) VALUES (?, 'Утренняя зарядка', 15)", (test_id,))
            cur.execute("INSERT INTO daily_habits (user_id, name, goal) VALUES (?, 'Медитация', 10)", (test_id,))

        conn.commit()

    conn.close()


def init_tasks_db():
    init_db(seed=True)


# ================================================================
# ЛОГИРОВАНИЕ ПОСЕЩЕНИЙ
# ================================================================

def log_visit(user_id=None, ip=None, user_agent=None, path=None):
    """Логирует посещение страницы."""
    conn = get_db()
    conn.execute(
        "INSERT INTO visits (user_id, ip, user_agent, path) VALUES (?, ?, ?, ?)",
        (user_id, ip, user_agent, path)
    )
    conn.commit()
    conn.close()


# ================================================================
# АДМИН-ФУНКЦИИ
# ================================================================

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором."""
    conn = get_db()
    row = conn.execute(
        "SELECT is_admin FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return bool(row and row["is_admin"])


def get_all_users():
    """Возвращает список всех пользователей."""
    conn = get_db()
    rows = conn.execute("""
        SELECT 
            u.id, u.username, u.display_name, u.is_admin, u.created_at,
            COUNT(DISTINCT v.id) as visits,
            COUNT(DISTINCT dh.id) as daily_habits,
            COUNT(DISTINCT wh.id) as weekly_habits,
            COUNT(DISTINCT mh.id) as monthly_habits,
            COUNT(DISTINCT g.id) as goals,
            COUNT(DISTINCT t.id) as tasks,
            (
                SELECT COUNT(*) FROM daily_entries de 
                JOIN daily_habits dh2 ON de.habit_id = dh2.id 
                WHERE dh2.user_id = u.id AND de.done = 1
            ) as done_daily
        FROM users u
        LEFT JOIN visits v ON u.id = v.user_id
        LEFT JOIN daily_habits dh ON u.id = dh.user_id
        LEFT JOIN weekly_habits wh ON u.id = wh.user_id
        LEFT JOIN monthly_habits mh ON u.id = mh.user_id
        LEFT JOIN goals g ON u.id = g.user_id
        LEFT JOIN tasks t ON u.id = t.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_stats(user_id):
    """Статистика конкретного пользователя."""
    conn = get_db()
    user = conn.execute(
        "SELECT id, username, display_name, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return None

    stats = dict(user)

    # Кол-во привычек
    stats['daily_habits'] = conn.execute(
        "SELECT COUNT(*) FROM daily_habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    stats['weekly_habits'] = conn.execute(
        "SELECT COUNT(*) FROM weekly_habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    stats['monthly_habits'] = conn.execute(
        "SELECT COUNT(*) FROM monthly_habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    stats['goals'] = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    stats['tasks'] = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    stats['tasks_done'] = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'Выполнено'", (user_id,)
    ).fetchone()[0]
    stats['visits'] = conn.execute(
        "SELECT COUNT(*) FROM visits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    # Прогресс по привычкам за текущий месяц
    now = date.today()
    stats['daily_done'] = conn.execute(
        """SELECT COUNT(*) FROM daily_entries de
           JOIN daily_habits dh ON de.habit_id = dh.id
           WHERE dh.user_id = ? AND de.year = ? AND de.month = ? AND de.done = 1""",
        (user_id, now.year, now.month)
    ).fetchone()[0]
    stats['daily_total'] = conn.execute(
        "SELECT COUNT(*) FROM daily_habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    conn.close()
    return stats


def get_admin_stats():
    """Общая статистика для админ-панели."""
    conn = get_db()

    # Основные метрики
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
    total_visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    today_visits = conn.execute(
        "SELECT COUNT(*) FROM visits WHERE date(visited_at) = date('now')"
    ).fetchone()[0]
    unique_visitors = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM visits WHERE user_id IS NOT NULL"
    ).fetchone()[0]

    # Статистика по дням (последние 30 дней)
    daily_visits = conn.execute("""
        SELECT date(visited_at) as day, COUNT(*) as count
        FROM visits
        WHERE visited_at >= date('now', '-30 days')
        GROUP BY date(visited_at)
        ORDER BY day
    """).fetchall()

    # Самые активные пользователи
    top_users = conn.execute("""
        SELECT 
            u.display_name,
            u.username,
            COUNT(v.id) as visits
        FROM users u
        JOIN visits v ON u.id = v.user_id
        GROUP BY u.id
        ORDER BY visits DESC
        LIMIT 10
    """).fetchall()

    # Активность по часам
    hourly_visits = conn.execute("""
        SELECT strftime('%H', visited_at) as hour, COUNT(*) as count
        FROM visits
        WHERE visited_at >= date('now', '-30 days')
        GROUP BY hour
        ORDER BY hour
    """).fetchall()

    # Статистика по типам контента
    content_stats = {
        'daily_habits': conn.execute("SELECT COUNT(*) FROM daily_habits").fetchone()[0],
        'weekly_habits': conn.execute("SELECT COUNT(*) FROM weekly_habits").fetchone()[0],
        'monthly_habits': conn.execute("SELECT COUNT(*) FROM monthly_habits").fetchone()[0],
        'goals': conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0],
        'tasks': conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        'tasks_done': conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'Выполнено'"
        ).fetchone()[0],
    }

    conn.close()

    return {
        'total_users': total_users,
        'total_admins': total_admins,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'unique_visitors': unique_visitors,
        'daily_visits': [dict(r) for r in daily_visits],
        'top_users': [dict(r) for r in top_users],
        'hourly_visits': [dict(r) for r in hourly_visits],
        'content_stats': content_stats,
    }


# ================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# ================================================================

def get_user_id():
    from flask import session
    return session.get('user_id')


# ================================================================
# ОСТАЛЬНЫЕ ФУНКЦИИ (ОБНОВЛЕНЫ С USER_ID)
# ================================================================

def get_daily_grid(user_id, year, month):
    habits = get_daily_habits(user_id)
    entries = get_daily_entries(user_id, year, month)
    ndays = calendar.monthrange(year, month)[1]
    return habits, entries, ndays


def get_daily_habits(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, goal FROM daily_habits WHERE user_id = ? ORDER BY sort_order, id",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_entries(user_id, year, month):
    conn = get_db()
    rows = conn.execute(
        """SELECT h.id as habit_id, e.day, e.done
           FROM daily_habits h
           LEFT JOIN daily_entries e ON h.id = e.habit_id AND e.year = ? AND e.month = ?
           WHERE h.user_id = ?""",
        (year, month, user_id)
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        if r["day"] is not None:
            result[(r["habit_id"], r["day"])] = r["done"]
    return result


def add_daily_habit(user_id, name, goal=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO daily_habits (user_id, name, goal) VALUES (?, ?, ?)",
        (user_id, name, goal)
    )
    conn.commit()
    conn.close()


def delete_daily_habit(user_id, habit_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM daily_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    )
    conn.commit()
    conn.close()


def toggle_daily_entry(user_id, habit_id, year, month, day):
    conn = get_db()
    habit = conn.execute(
        "SELECT id FROM daily_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    ).fetchone()
    if not habit:
        conn.close()
        return False

    existing = conn.execute(
        "SELECT done FROM daily_entries WHERE habit_id=? AND year=? AND month=? AND day=?",
        (habit_id, year, month, day)
    ).fetchone()
    if existing:
        new_done = 0 if existing["done"] == 1 else 1
        conn.execute(
            "UPDATE daily_entries SET done=? WHERE habit_id=? AND year=? AND month=? AND day=?",
            (new_done, habit_id, year, month, day)
        )
    else:
        new_done = 1
        conn.execute(
            "INSERT INTO daily_entries (habit_id, year, month, day, done) VALUES (?, ?, ?, ?, 1)",
            (habit_id, year, month, day)
        )
    conn.commit()
    conn.close()
    return bool(new_done)


def get_weekly_grid(user_id, year, month):
    habits = get_weekly_habits(user_id)
    entries = get_weekly_entries(user_id, year, month)
    nweeks = 5
    return habits, entries, nweeks


def get_weekly_habits(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name FROM weekly_habits WHERE user_id = ? ORDER BY sort_order, id",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_entries(user_id, year, month):
    conn = get_db()
    rows = conn.execute(
        """SELECT h.id as habit_id, e.week, e.done
           FROM weekly_habits h
           LEFT JOIN weekly_entries e ON h.id = e.habit_id AND e.year = ? AND e.month = ?
           WHERE h.user_id = ?""",
        (year, month, user_id)
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        if r["week"] is not None:
            result[(r["habit_id"], r["week"])] = r["done"]
    return result


def add_weekly_habit(user_id, name):
    conn = get_db()
    conn.execute(
        "INSERT INTO weekly_habits (user_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    conn.commit()
    conn.close()


def delete_weekly_habit(user_id, habit_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM weekly_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    )
    conn.commit()
    conn.close()


def toggle_weekly_entry(user_id, habit_id, year, month, week):
    conn = get_db()
    habit = conn.execute(
        "SELECT id FROM weekly_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    ).fetchone()
    if not habit:
        conn.close()
        return False

    existing = conn.execute(
        "SELECT done FROM weekly_entries WHERE habit_id=? AND year=? AND month=? AND week=?",
        (habit_id, year, month, week)
    ).fetchone()
    if existing:
        new_done = 0 if existing["done"] else 1
        conn.execute(
            "UPDATE weekly_entries SET done=? WHERE habit_id=? AND year=? AND month=? AND week=?",
            (new_done, habit_id, year, month, week)
        )
    else:
        new_done = 1
        conn.execute(
            "INSERT INTO weekly_entries (habit_id, year, month, week, done) VALUES (?, ?, ?, ?, 1)",
            (habit_id, year, month, week)
        )
    conn.commit()
    conn.close()
    return bool(new_done)


def get_monthly_list(user_id, year, month):
    habits = get_monthly_habits(user_id)
    entries = get_monthly_entries(user_id, year, month)
    return habits, entries


def get_monthly_habits(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name FROM monthly_habits WHERE user_id = ? ORDER BY sort_order, id",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_entries(user_id, year, month):
    conn = get_db()
    rows = conn.execute(
        """SELECT h.id as habit_id, e.done
           FROM monthly_habits h
           LEFT JOIN monthly_entries e ON h.id = e.habit_id AND e.year = ? AND e.month = ?
           WHERE h.user_id = ?""",
        (year, month, user_id)
    ).fetchall()
    conn.close()
    return {r["habit_id"]: r["done"] for r in rows if r["done"] is not None}


def add_monthly_habit(user_id, name):
    conn = get_db()
    conn.execute(
        "INSERT INTO monthly_habits (user_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    conn.commit()
    conn.close()


def delete_monthly_habit(user_id, habit_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM monthly_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    )
    conn.commit()
    conn.close()


def toggle_monthly_entry(user_id, habit_id, year, month):
    conn = get_db()
    habit = conn.execute(
        "SELECT id FROM monthly_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    ).fetchone()
    if not habit:
        conn.close()
        return False

    existing = conn.execute(
        "SELECT done FROM monthly_entries WHERE habit_id=? AND year=? AND month=?",
        (habit_id, year, month)
    ).fetchone()
    if existing:
        new_done = 0 if existing["done"] else 1
        conn.execute(
            "UPDATE monthly_entries SET done=? WHERE habit_id=? AND year=? AND month=?",
            (new_done, habit_id, year, month)
        )
    else:
        new_done = 1
        conn.execute(
            "INSERT INTO monthly_entries (habit_id, year, month, done) VALUES (?, ?, ?, 1)",
            (habit_id, year, month)
        )
    conn.commit()
    conn.close()
    return bool(new_done)


def get_goals(user_id):
    conn = get_db()
    goal_rows = conn.execute(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    goals = []
    total = 0
    done_total = 0
    for g in goal_rows:
        goal = dict(g)
        steps = conn.execute(
            "SELECT * FROM goal_steps WHERE goal_id=? ORDER BY id",
            (g["id"],)
        ).fetchall()
        goal["steps"] = [dict(s) for s in steps]
        done_steps = sum(1 for s in goal["steps"] if s["done"])
        total_steps = len(goal["steps"]) if goal["steps"] else 1
        goal["progress"] = (done_steps / total_steps * 100) if total_steps else 0
        total += 1
        if g["status"] == "done":
            done_total += 1
        goals.append(goal)

    spheres = {}
    for g in goals:
        sp = g.get("sphere") or "Без сферы"
        spheres.setdefault(sp, [0, 0])
        spheres[sp][1] += 1
        if g["status"] == "done":
            spheres[sp][0] += 1
    conn.close()
    overall_pct = round(done_total / total * 100) if total else 0
    return goals, spheres, done_total, total, overall_pct


def add_goal(user_id, title, sphere, reward, deadline):
    conn = get_db()
    conn.execute(
        "INSERT INTO goals (user_id, title, sphere, reward, deadline) VALUES (?, ?, ?, ?, ?)",
        (user_id, title, sphere, reward, deadline)
    )
    conn.commit()
    conn.close()


def delete_goal(user_id, goal_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id)
    )
    conn.commit()
    conn.close()


def set_goal_status(user_id, goal_id, status):
    conn = get_db()
    conn.execute(
        "UPDATE goals SET status=? WHERE id = ? AND user_id = ?",
        (status, goal_id, user_id)
    )
    conn.commit()
    conn.close()


def add_goal_step(user_id, goal_id, text):
    conn = get_db()
    goal = conn.execute(
        "SELECT id FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id)
    ).fetchone()
    if goal:
        conn.execute(
            "INSERT INTO goal_steps (goal_id, text) VALUES (?, ?)",
            (goal_id, text)
        )
        conn.commit()
    conn.close()


def toggle_goal_step(user_id, step_id):
    conn = get_db()
    step = conn.execute(
        """SELECT s.done, s.id
           FROM goal_steps s
           JOIN goals g ON s.goal_id = g.id
           WHERE s.id = ? AND g.user_id = ?""",
        (step_id, user_id)
    ).fetchone()
    if step:
        new_done = 0 if step["done"] else 1
        conn.execute(
            "UPDATE goal_steps SET done=? WHERE id=?",
            (new_done, step_id)
        )
        conn.commit()
        conn.close()
        return bool(new_done)
    conn.close()
    return False


def get_tasks(user_id, status=None, priority=None, assignee=None, category=None, q=None):
    conn = get_db()
    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [user_id]
    if status:
        query += " AND status=?"
        params.append(status)
    if priority:
        query += " AND priority=?"
        params.append(priority)
    if assignee:
        query += " AND assignee=?"
        params.append(assignee)
    if category:
        query += " AND category=?"
        params.append(category)
    if q:
        query += " AND title LIKE ?"
        params.append("%" + q + "%")
    query += " ORDER BY due_date IS NULL, due_date ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    tasks = []
    for r in rows:
        t = dict(r)
        t["overdue"] = False
        if t["due_date"]:
            try:
                due = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                t["days_left"] = (due - date.today()).days
                t["overdue"] = t["days_left"] < 0
            except:
                t["days_left"] = None
        else:
            t["days_left"] = None
        tasks.append(t)
    return tasks


def add_task(user_id, title, due_date, assignee, status, category, priority, important, urgent, description):
    conn = get_db()
    conn.execute(
        """INSERT INTO tasks (user_id, title, due_date, assignee, status, category, priority, important, urgent, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, title, due_date, assignee, status, category, priority, int(important), int(urgent), description)
    )
    conn.commit()
    conn.close()


def delete_task(user_id, task_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, user_id)
    )
    conn.commit()
    conn.close()


def update_task(user_id, task_id, **fields):
    conn = get_db()
    if fields:
        set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
        values = list(fields.values()) + [task_id, user_id]
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id=? AND user_id=?",
            values
        )
    conn.commit()
    conn.close()


def task_stats(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks WHERE user_id = ? GROUP BY status",
        (user_id,)
    ).fetchall()
    status_counts = {s: 0 for s in STATUSES}
    for r in rows:
        status_counts[r["status"]] = r["cnt"]
    total = sum(status_counts.values())
    done = status_counts.get("Выполнено", 0)
    in_progress = status_counts.get("В процессе", 0)
    overdue = 0
    due7 = 0
    due14 = 0
    due30 = 0
    upcoming = []
    tasks = get_tasks(user_id)
    for t in tasks:
        if t["overdue"]:
            overdue += 1
        if t["days_left"] is not None and t["days_left"] <= 7:
            due7 += 1
        if t["days_left"] is not None and t["days_left"] <= 14:
            due14 += 1
        if t["days_left"] is not None and t["days_left"] <= 30:
            due30 += 1
        if t["due_date"] and t["status"] != "Выполнено":
            upcoming.append(t)
    upcoming = sorted(upcoming, key=lambda x: x["due_date"])[:8]

    priority_counts = {p: 0 for p in PRIORITIES}
    for t in tasks:
        priority_counts[t["priority"]] += 1

    workload = {}
    for t in tasks:
        if t["assignee"] and t["status"] != "Выполнено":
            workload[t["assignee"]] = workload.get(t["assignee"], 0) + 1

    conn.close()

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "overdue": overdue,
        "due7": due7,
        "due14": due14,
        "due30": due30,
        "progress_pct": (done / total * 100) if total else 0,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "upcoming": upcoming,
        "workload": workload
    }


def matrix_tasks(user_id, assignee=None):
    tasks = get_tasks(user_id, assignee=assignee)
    quads = {
        "Сделать сейчас": [],
        "Запланировать": [],
        "Делегировать": [],
        "Исключить": []
    }
    pct = {k: 0 for k in quads}
    for t in tasks:
        if t["important"] and t["urgent"]:
            quads["Сделать сейчас"].append(t)
        elif t["important"]:
            quads["Запланировать"].append(t)
        elif t["urgent"]:
            quads["Делегировать"].append(t)
        else:
            quads["Исключить"].append(t)
    total = len(tasks) if tasks else 1
    for k in quads:
        pct[k] = (len(quads[k]) / total * 100) if total else 0
    return quads, pct


def calendar_tasks(user_id, year, month):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND due_date LIKE ?",
        (user_id, f"{year:04d}-{month:02d}-%")
    ).fetchall()
    conn.close()
    by_day = {}
    for r in rows:
        t = dict(r)
        try:
            day = int(t["due_date"].split("-")[2])
        except:
            day = None
        if day:
            t["overdue"] = t["due_date"] < date.today().isoformat()
            by_day.setdefault(day, []).append(t)
    return by_day


def get_schedule(user_id, date_str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM schedule WHERE user_id = ? AND date = ?",
        (user_id, date_str)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_schedule_entry(user_id, date_str, time_str, task_id=None, note=""):
    conn = get_db()
    existing = conn.execute(
        "SELECT 1 FROM schedule WHERE user_id = ? AND date = ? AND time = ?",
        (user_id, date_str, time_str)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE schedule SET task_id=?, note=? WHERE user_id=? AND date=? AND time=?",
            (task_id, note, user_id, date_str, time_str)
        )
    else:
        conn.execute(
            "INSERT INTO schedule (user_id, date, time, task_id, note) VALUES (?, ?, ?, ?, ?)",
            (user_id, date_str, time_str, task_id, note)
        )
    conn.commit()
    conn.close()


def distinct_values(user_id, field):
    conn = get_db()
    rows = conn.execute(
        f"SELECT DISTINCT {field} FROM tasks WHERE user_id = ? AND {field} IS NOT NULL AND {field} != ''",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ================================================================
# СТАТУСЫ ОТМЕТОК ЕЖЕДНЕВНЫХ ПРИВЫЧЕК
#   0 — не отмечено, 1 — выполнено, 2 — пропуск (день отдыха / пауза:
#   не считается выполнением, но и не обрывает серию)
# ================================================================
STATE_EMPTY, STATE_DONE, STATE_SKIP = 0, 1, 2


def set_daily_entry(user_id, habit_id, year, month, day, state):
    """Ставит отметке конкретное состояние (0/1/2). Возвращает итоговое состояние."""
    state = int(state)
    if state not in (STATE_EMPTY, STATE_DONE, STATE_SKIP):
        state = STATE_EMPTY
    conn = get_db()
    habit = conn.execute(
        "SELECT id FROM daily_habits WHERE id = ? AND user_id = ?",
        (habit_id, user_id)
    ).fetchone()
    if not habit:
        conn.close()
        return STATE_EMPTY
    conn.execute(
        # INSERT OR REPLACE вместо UPSERT — работает и на старом SQLite хостинга
        "INSERT OR REPLACE INTO daily_entries (habit_id, year, month, day, done) VALUES (?, ?, ?, ?, ?)",
        (habit_id, year, month, day, state)
    )
    conn.commit()
    conn.close()
    return state


def get_daily_history(user_id):
    """Вся история отметок: {habit_id: {date: state}}."""
    conn = get_db()
    rows = conn.execute(
        """SELECT e.habit_id, e.year, e.month, e.day, e.done
           FROM daily_entries e JOIN daily_habits h ON h.id = e.habit_id
           WHERE h.user_id = ? AND e.done IN (1, 2)""",
        (user_id,)
    ).fetchall()
    conn.close()
    hist = {}
    for r in rows:
        try:
            d = date(r["year"], r["month"], r["day"])
        except ValueError:
            continue
        hist.setdefault(r["habit_id"], {})[d] = r["done"]
    return hist


def habit_streaks(user_id, today=None):
    """Текущая и лучшая серия по каждой ежедневной привычке.

    Серия — дни подряд с отметкой «выполнено». «Пропуск» серию не рвёт и не
    удлиняет. Сегодняшний день ещё не прошёл, поэтому если сегодня не
    отмечено, текущая серия считается по вчерашний день.
    """
    from datetime import timedelta
    today = today or date.today()
    hist = get_daily_history(user_id)
    result = {}
    for h in get_daily_habits(user_id):
        marks = hist.get(h["id"], {})
        # лучшая серия
        best = run = 0
        if marks:
            d = min(marks)
            last = max(max(marks), today)
            while d <= last:
                st = marks.get(d, 0)
                if st == STATE_DONE:
                    run += 1
                    best = max(best, run)
                elif st != STATE_SKIP and d != today:
                    run = 0
                d += timedelta(days=1)
        # текущая серия
        cur = 0
        d = today if marks.get(today) else today - timedelta(days=1)
        while True:
            st = marks.get(d, 0)
            if st == STATE_DONE:
                cur += 1
            elif st != STATE_SKIP:
                break
            d -= timedelta(days=1)
            if marks and d < min(marks):
                break
        result[h["id"]] = {"current": cur, "best": max(best, cur)}
    return result


def export_daily_rows(user_id):
    """Строки для CSV-выгрузки: дата, привычка, статус."""
    names = {h["id"]: h["name"] for h in get_daily_habits(user_id)}
    labels = {STATE_DONE: "выполнено", STATE_SKIP: "пропуск"}
    rows = []
    for hid, marks in get_daily_history(user_id).items():
        for d, st in marks.items():
            rows.append((d.isoformat(), names.get(hid, ""), labels.get(st, "")))
    rows.sort()
    return rows


# Готовые привычки для быстрого старта (по сферам)
HABIT_LIBRARY = [
    ("Здоровье", ["Выпить 2 л воды", "Зарядка 10 минут", "8 часов сна", "10 000 шагов"]),
    ("Развитие", ["Читать 20 минут", "Английский 15 минут", "Конспект дня"]),
    ("Спокойствие", ["Медитация 5 минут", "Без телефона перед сном", "Прогулка"]),
    ("Дела", ["План на завтра", "Разобрать почту", "Учёт расходов"]),
]


def daily_stats(user_id, year, month, today=None):
    today = today or date.today()
    habits = get_daily_habits(user_id)
    entries = get_daily_entries(user_id, year, month)
    ndays = calendar.monthrange(year, month)[1]

    def goal_of(h):
        return h["goal"] if h["goal"] else ndays

    total_goal = sum(goal_of(h) for h in habits)
    total_done = sum(1 for v in entries.values() if v == STATE_DONE)

    day_percent = []
    for day in range(1, ndays + 1):
        done = sum(1 for h in habits if entries.get((h["id"], day)) == STATE_DONE)
        skipped = sum(1 for h in habits if entries.get((h["id"], day)) == STATE_SKIP)
        active = len(habits) - skipped
        day_percent.append(round(done / active * 100) if active > 0 else 0)

    per_habit = {}
    top = []
    for h in habits:
        done_count = sum(1 for d in range(1, ndays + 1) if entries.get((h["id"], d)) == STATE_DONE)
        pct = min(100, round(done_count / goal_of(h) * 100)) if goal_of(h) else 0
        per_habit[h["id"]] = {"done": done_count, "goal": goal_of(h), "percent": pct}
        top.append({"name": h["name"], "percent": pct})
    top10 = sorted(top, key=lambda x: -x["percent"])[:10]

    is_current = (year, month) == (today.year, today.month)
    today_done = sum(1 for h in habits if entries.get((h["id"], today.day)) == STATE_DONE) if is_current else None

    return {
        "total_done": total_done,
        "total_goal": total_goal,
        "overall_pct": min(100, round(total_done / total_goal * 100)) if total_goal else 0,
        "day_percent": day_percent,
        "top10": top10,
        "per_habit": per_habit,
        "today_done": today_done,
        "habits_count": len(habits),
    }


def weekly_stats(user_id, year, month, week):
    habits = get_weekly_habits(user_id)
    entries = get_weekly_entries(user_id, year, month)
    total = len(habits)
    done = sum(1 for (hid, w), v in entries.items() if w == week and v)
    return {
        "total": total,
        "done": done,
        "percent": round(done / total * 100) if total else 0
    }


def monthly_stats(user_id, year, month):
    habits = get_monthly_habits(user_id)
    entries = get_monthly_entries(user_id, year, month)
    total = len(habits)
    done = sum(1 for hid, v in entries.items() if v)
    return {
        "total": total,
        "done": done,
        "percent": round(done / total * 100) if total else 0
    }