"""
Слой работы с БД для Трекера Привычек.
Использую обычный sqlite3 (без ORM) — база компактная, запросы простые.
"""
import sqlite3
import calendar
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "habit_tracker.db"

MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=True):
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS daily_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        goal INTEGER,               -- сколько раз в месяц планируется (NULL = каждый день)
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS daily_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL REFERENCES daily_habits(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        UNIQUE(habit_id, year, month, day)
    );
    CREATE TABLE IF NOT EXISTS weekly_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS weekly_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL REFERENCES weekly_habits(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        week_number INTEGER NOT NULL,   -- 1..5
        done INTEGER NOT NULL DEFAULT 0,
        UNIQUE(habit_id, year, month, week_number)
    );
    CREATE TABLE IF NOT EXISTS monthly_habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS monthly_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL REFERENCES monthly_habits(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        UNIQUE(habit_id, year, month)
    );
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        sphere TEXT NOT NULL DEFAULT 'Личностный рост',
        reward TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | done
        deadline TEXT DEFAULT '',
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS goal_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER DEFAULT 0
    );
    """)
    conn.commit()

    if seed:
        cur.execute("SELECT COUNT(*) FROM daily_habits")
        if cur.fetchone()[0] == 0:
            defaults = ["Встать в 6 утра", "Спорт 30 минут", "Медитация", "Чтение",
                        "Полезный завтрак", "Планирование дня", "Проверить почту",
                        "Работа", "Прогулка", "Здоровый сон"]
            for i, name in enumerate(defaults):
                cur.execute("INSERT INTO daily_habits (name, goal, sort_order) VALUES (?,?,?)",
                            (name, None, i))
        cur.execute("SELECT COUNT(*) FROM weekly_habits")
        if cur.fetchone()[0] == 0:
            for i, name in enumerate(["Встретиться с друзьями", "Спланировать рацион", "Заказать еду домой"]):
                cur.execute("INSERT INTO weekly_habits (name, sort_order) VALUES (?,?)", (name, i))
        cur.execute("SELECT COUNT(*) FROM monthly_habits")
        if cur.fetchone()[0] == 0:
            for i, name in enumerate(["Генеральная уборка по дому", "Планирование месяца", "Почистить почту"]):
                cur.execute("INSERT INTO monthly_habits (name, sort_order) VALUES (?,?)", (name, i))
        cur.execute("SELECT COUNT(*) FROM goals")
        if cur.fetchone()[0] == 0:
            cur.execute("""INSERT INTO goals (title, sphere, reward, status, deadline, sort_order)
                            VALUES (?,?,?,?,?,?)""",
                        ("Закрыть кредитку", "Финансы", "Отправиться в путешествие", "done", "2025-01-01", 0))
            cur.execute("""INSERT INTO goals (title, sphere, reward, status, deadline, sort_order)
                            VALUES (?,?,?,?,?,?)""",
                        ("Получить повышение", "Карьера", "Спа и массаж", "in_progress", "2026-01-01", 1))
        conn.commit()
    conn.close()


# ---------- ДНЕВНЫЕ ПРИВЫЧКИ ----------

def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def get_daily_habits():
    conn = get_db()
    rows = conn.execute("SELECT * FROM daily_habits ORDER BY sort_order, id").fetchall()
    conn.close()
    return rows


def get_daily_grid(year, month):
    """Возвращает (habits, entries_map, ndays) где entries_map[(habit_id, day)] = done(bool)"""
    conn = get_db()
    habits = conn.execute("SELECT * FROM daily_habits ORDER BY sort_order, id").fetchall()
    rows = conn.execute(
        "SELECT habit_id, day, done FROM daily_entries WHERE year=? AND month=?",
        (year, month)).fetchall()
    conn.close()
    entries = {(r["habit_id"], r["day"]): bool(r["done"]) for r in rows}
    return habits, entries, days_in_month(year, month)


def toggle_daily_entry(habit_id, year, month, day):
    conn = get_db()
    row = conn.execute(
        "SELECT done FROM daily_entries WHERE habit_id=? AND year=? AND month=? AND day=?",
        (habit_id, year, month, day)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO daily_entries (habit_id, year, month, day, done) VALUES (?,?,?,?,1)",
            (habit_id, year, month, day))
        new_done = True
    else:
        new_done = not bool(row["done"])
        conn.execute(
            "UPDATE daily_entries SET done=? WHERE habit_id=? AND year=? AND month=? AND day=?",
            (int(new_done), habit_id, year, month, day))
    conn.commit()
    conn.close()
    return new_done


def add_daily_habit(name, goal=None):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM daily_habits").fetchone()[0]
    conn.execute("INSERT INTO daily_habits (name, goal, sort_order) VALUES (?,?,?)",
                 (name.strip(), goal, max_order + 1))
    conn.commit()
    conn.close()


def delete_daily_habit(habit_id):
    conn = get_db()
    conn.execute("DELETE FROM daily_habits WHERE id=?", (habit_id,))
    conn.commit()
    conn.close()


def daily_stats(year, month):
    """Считает: % по дням (для графика), % по привычкам, топ-10, общий прогресс."""
    habits, entries, ndays = get_daily_grid(year, month)
    n_habits = len(habits)

    day_percent = []
    for d in range(1, ndays + 1):
        if n_habits == 0:
            day_percent.append(0)
            continue
        done_count = sum(1 for h in habits if entries.get((h["id"], d), False))
        day_percent.append(round(done_count / n_habits * 100))

    habit_rows = []
    for h in habits:
        goal = h["goal"] if h["goal"] else ndays
        done_count = sum(1 for d in range(1, ndays + 1) if entries.get((h["id"], d), False))
        pct = round(done_count / goal * 100) if goal else 0
        habit_rows.append({"id": h["id"], "name": h["name"], "goal": goal,
                            "done": done_count, "percent": pct})

    top10 = sorted(habit_rows, key=lambda r: r["percent"], reverse=True)[:10]
    total_done = sum(r["done"] for r in habit_rows)
    total_goal = sum(r["goal"] for r in habit_rows)
    overall_pct = round(total_done / total_goal * 100) if total_goal else 0

    return {
        "day_percent": day_percent,
        "habit_rows": habit_rows,
        "top10": top10,
        "overall_pct": overall_pct,
        "total_done": total_done,
        "total_goal": total_goal,
        "ndays": ndays,
    }


# ---------- ЕЖЕНЕДЕЛЬНЫЕ ПРИВЫЧКИ ----------

def n_weeks_in_month(year, month):
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return len(weeks)


def get_weekly_grid(year, month):
    conn = get_db()
    habits = conn.execute("SELECT * FROM weekly_habits ORDER BY sort_order, id").fetchall()
    rows = conn.execute(
        "SELECT habit_id, week_number, done FROM weekly_entries WHERE year=? AND month=?",
        (year, month)).fetchall()
    conn.close()
    entries = {(r["habit_id"], r["week_number"]): bool(r["done"]) for r in rows}
    return habits, entries, n_weeks_in_month(year, month)


def toggle_weekly_entry(habit_id, year, month, week_number):
    conn = get_db()
    row = conn.execute(
        "SELECT done FROM weekly_entries WHERE habit_id=? AND year=? AND month=? AND week_number=?",
        (habit_id, year, month, week_number)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO weekly_entries (habit_id, year, month, week_number, done) VALUES (?,?,?,?,1)",
            (habit_id, year, month, week_number))
        new_done = True
    else:
        new_done = not bool(row["done"])
        conn.execute(
            "UPDATE weekly_entries SET done=? WHERE habit_id=? AND year=? AND month=? AND week_number=?",
            (int(new_done), habit_id, year, month, week_number))
    conn.commit()
    conn.close()
    return new_done


def add_weekly_habit(name):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM weekly_habits").fetchone()[0]
    conn.execute("INSERT INTO weekly_habits (name, sort_order) VALUES (?,?)", (name.strip(), max_order + 1))
    conn.commit()
    conn.close()


def delete_weekly_habit(habit_id):
    conn = get_db()
    conn.execute("DELETE FROM weekly_habits WHERE id=?", (habit_id,))
    conn.commit()
    conn.close()


def weekly_stats(year, month, week_number):
    habits, entries, nweeks = get_weekly_grid(year, month)
    total = len(habits)
    done = sum(1 for h in habits if entries.get((h["id"], week_number), False))
    pct = round(done / total * 100) if total else 0
    return {"done": done, "total": total, "percent": pct, "nweeks": nweeks}


# ---------- ЕЖЕМЕСЯЧНЫЕ ПРИВЫЧКИ ----------

def get_monthly_list(year, month):
    conn = get_db()
    habits = conn.execute("SELECT * FROM monthly_habits ORDER BY sort_order, id").fetchall()
    rows = conn.execute(
        "SELECT habit_id, done FROM monthly_entries WHERE year=? AND month=?",
        (year, month)).fetchall()
    conn.close()
    entries = {r["habit_id"]: bool(r["done"]) for r in rows}
    return habits, entries


def toggle_monthly_entry(habit_id, year, month):
    conn = get_db()
    row = conn.execute(
        "SELECT done FROM monthly_entries WHERE habit_id=? AND year=? AND month=?",
        (habit_id, year, month)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO monthly_entries (habit_id, year, month, done) VALUES (?,?,?,1)",
            (habit_id, year, month))
        new_done = True
    else:
        new_done = not bool(row["done"])
        conn.execute(
            "UPDATE monthly_entries SET done=? WHERE habit_id=? AND year=? AND month=?",
            (int(new_done), habit_id, year, month))
    conn.commit()
    conn.close()
    return new_done


def add_monthly_habit(name):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM monthly_habits").fetchone()[0]
    conn.execute("INSERT INTO monthly_habits (name, sort_order) VALUES (?,?)", (name.strip(), max_order + 1))
    conn.commit()
    conn.close()


def delete_monthly_habit(habit_id):
    conn = get_db()
    conn.execute("DELETE FROM monthly_habits WHERE id=?", (habit_id,))
    conn.commit()
    conn.close()


def monthly_stats(year, month):
    habits, entries = get_monthly_list(year, month)
    total = len(habits)
    done = sum(1 for h in habits if entries.get(h["id"], False))
    pct = round(done / total * 100) if total else 0
    return {"done": done, "total": total, "percent": pct}


# ---------- ЦЕЛИ ----------

def get_goals():
    conn = get_db()
    goals = conn.execute("SELECT * FROM goals ORDER BY sort_order, id").fetchall()
    result = []
    spheres = {}
    for g in goals:
        steps = conn.execute("SELECT * FROM goal_steps WHERE goal_id=? ORDER BY sort_order, id",
                              (g["id"],)).fetchall()
        gd = dict(g)
        gd["steps"] = [dict(s) for s in steps]
        n_steps = len(steps)
        done_steps = sum(1 for s in steps if s["done"])
        gd["progress"] = round(done_steps / n_steps * 100) if n_steps else (100 if g["status"] == "done" else 0)
        result.append(gd)
        spheres.setdefault(g["sphere"], [0, 0])
        spheres[g["sphere"]][1] += 1
        if g["status"] == "done":
            spheres[g["sphere"]][0] += 1
    conn.close()
    total = len(result)
    done_total = sum(1 for g in result if g["status"] == "done")
    overall_pct = round(done_total / total * 100) if total else 0
    return result, spheres, done_total, total, overall_pct


def add_goal(title, sphere, reward, deadline):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM goals").fetchone()[0]
    conn.execute("""INSERT INTO goals (title, sphere, reward, status, deadline, sort_order)
                     VALUES (?,?,?,?,?,?)""",
                 (title.strip(), sphere.strip() or "Личностный рост", reward.strip(), "in_progress",
                  deadline.strip(), max_order + 1))
    conn.commit()
    conn.close()


def delete_goal(goal_id):
    conn = get_db()
    conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()
    conn.close()


def set_goal_status(goal_id, status):
    conn = get_db()
    conn.execute("UPDATE goals SET status=? WHERE id=?", (status, goal_id))
    conn.commit()
    conn.close()


def add_goal_step(goal_id, text):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM goal_steps WHERE goal_id=?",
                              (goal_id,)).fetchone()[0]
    conn.execute("INSERT INTO goal_steps (goal_id, text, sort_order) VALUES (?,?,?)",
                 (goal_id, text.strip(), max_order + 1))
    conn.commit()
    conn.close()


def toggle_goal_step(step_id):
    conn = get_db()
    row = conn.execute("SELECT done FROM goal_steps WHERE id=?", (step_id,)).fetchone()
    new_done = not bool(row["done"])
    conn.execute("UPDATE goal_steps SET done=? WHERE id=?", (int(new_done), step_id))
    conn.commit()
    conn.close()
    return new_done


# ================================================================
# ТРЕКЕР ЗАДАЧ (tasks / kanban / eisenhower / calendar / planner)
# ================================================================

STATUSES = ["Не начато", "В процессе", "В ожидании", "Приостановлено", "Выполнено"]
PRIORITIES = ["Низкий", "Средний", "Высокий", "Критичный"]
STATUS_ICON = {"Не начато": "○", "В процессе": "◐", "В ожидании": "⏳",
               "Приостановлено": "⏸", "Выполнено": "✓"}


def init_tasks_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        due_date TEXT,
        assignee TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Не начато',
        category TEXT DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'Средний',
        important INTEGER NOT NULL DEFAULT 0,
        urgent INTEGER NOT NULL DEFAULT 0,
        description TEXT DEFAULT '',
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS schedule_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time_label TEXT NOT NULL,
        task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
        note TEXT DEFAULT '',
        UNIQUE(date, time_label)
    );
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM tasks")
    if cur.fetchone()[0] == 0:
        from datetime import timedelta
        t = date.today()
        seed = [
            ("Проверить почту", (t + timedelta(days=1)).isoformat(), "Артём", "В процессе", "Работа/Учёба", "Высокий", 1, 1, ""),
            ("10 минут растяжки", (t + timedelta(days=3)).isoformat(), "Оля", "В процессе", "Здоровье и спорт", "Средний", 0, 0, ""),
            ("Сделать зарядку", (t + timedelta(days=4)).isoformat(), "Егор", "Не начато", "Здоровье и спорт", "Высокий", 1, 0, ""),
            ("Медитация 5 минут", (t + timedelta(days=4)).isoformat(), "Алёна", "В процессе", "Саморазвитие", "Критичный", 1, 1, ""),
            ("Записать расходы за день", (t + timedelta(days=5)).isoformat(), "Артём", "Не начато", "Финансы", "Критичный", 1, 1, ""),
            ("Проверить календарь на встречи", (t + timedelta(days=7)).isoformat(), "Оля", "В ожидании", "Встречи", "Высокий", 1, 1, ""),
            ("Подготовить обед", (t + timedelta(days=8)).isoformat(), "Алёна", "В процессе", "Домашние дела", "Средний", 0, 0, ""),
            ("Заполнить дневник благодарности", (t + timedelta(days=9)).isoformat(), "Оля", "Не начато", "Личное", "Средний", 0, 0, ""),
        ]
        for i, s in enumerate(seed):
            cur.execute("""INSERT INTO tasks (title, due_date, assignee, status, category, priority,
                            important, urgent, description, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (*s, i))
        conn.commit()
    conn.close()


def _task_row_to_dict(r, today):
    d = dict(r)
    if d["due_date"]:
        due = date.fromisoformat(d["due_date"])
        d["days_left"] = (due - today).days
        d["overdue"] = due < today and d["status"] != "Выполнено"
    else:
        d["days_left"] = None
        d["overdue"] = False
    if d["important"] and d["urgent"]:
        d["quadrant"] = "Сделать сейчас"
    elif d["important"] and not d["urgent"]:
        d["quadrant"] = "Запланировать"
    elif not d["important"] and d["urgent"]:
        d["quadrant"] = "Делегировать"
    else:
        d["quadrant"] = "Исключить"
    return d


def get_tasks(status=None, priority=None, assignee=None, category=None, q=None):
    conn = get_db()
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"; params.append(status)
    if priority:
        sql += " AND priority=?"; params.append(priority)
    if assignee:
        sql += " AND assignee=?"; params.append(assignee)
    if category:
        sql += " AND category=?"; params.append(category)
    if q:
        sql += " AND title LIKE ?"; params.append(f"%{q}%")
    sql += " ORDER BY sort_order, id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    today = date.today()
    return [_task_row_to_dict(r, today) for r in rows]


def get_task(task_id):
    conn = get_db()
    r = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return _task_row_to_dict(r, date.today()) if r else None


def add_task(title, due_date, assignee, status, category, priority, important, urgent, description):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM tasks").fetchone()[0]
    conn.execute("""INSERT INTO tasks (title, due_date, assignee, status, category, priority,
                     important, urgent, description, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (title.strip(), due_date or None, assignee.strip(), status, category.strip(),
                  priority, int(important), int(urgent), description.strip(), max_order + 1))
    conn.commit()
    conn.close()


def update_task(task_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    conn = get_db()
    conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def distinct_values(col):
    conn = get_db()
    rows = conn.execute(f"SELECT DISTINCT {col} FROM tasks WHERE {col}!='' ORDER BY {col}").fetchall()
    conn.close()
    return [r[0] for r in rows]


def task_stats():
    tasks = get_tasks()
    total = len(tasks)
    in_progress = sum(1 for t in tasks if t["status"] == "В процессе")
    done = sum(1 for t in tasks if t["status"] == "Выполнено")
    overdue = sum(1 for t in tasks if t["overdue"])
    due7 = sum(1 for t in tasks if t["days_left"] is not None and 0 <= t["days_left"] <= 7 and t["status"] != "Выполнено")
    due14 = sum(1 for t in tasks if t["days_left"] is not None and 0 <= t["days_left"] <= 14 and t["status"] != "Выполнено")
    due30 = sum(1 for t in tasks if t["days_left"] is not None and 0 <= t["days_left"] <= 30 and t["status"] != "Выполнено")
    progress_pct = round(done / total * 100) if total else 0

    status_counts = {s: sum(1 for t in tasks if t["status"] == s) for s in STATUSES}
    priority_counts = {p: sum(1 for t in tasks if t["priority"] == p) for p in PRIORITIES}
    workload = {}
    for t in tasks:
        if t["assignee"]:
            workload[t["assignee"]] = workload.get(t["assignee"], 0) + (1 if t["status"] != "Выполнено" else 0)

    upcoming = sorted([t for t in tasks if t["due_date"] and t["status"] != "Выполнено"],
                       key=lambda t: t["due_date"])[:6]

    return {
        "total": total, "in_progress": in_progress, "done": done, "overdue": overdue,
        "due7": due7, "due14": due14, "due30": due30, "progress_pct": progress_pct,
        "status_counts": status_counts, "priority_counts": priority_counts,
        "workload": workload, "upcoming": upcoming,
    }


def matrix_tasks(assignee=None):
    tasks = get_tasks(assignee=assignee)
    tasks = [t for t in tasks if t["status"] != "Выполнено"]
    quads = {"Сделать сейчас": [], "Запланировать": [], "Делегировать": [], "Исключить": []}
    for t in tasks:
        quads[t["quadrant"]].append(t)
    total = len(tasks) or 1
    pct = {k: round(len(v) / total * 100) for k, v in quads.items()}
    return quads, pct


def calendar_tasks(year, month):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE due_date LIKE ? ORDER BY due_date",
        (f"{year:04d}-{month:02d}-%",)).fetchall()
    conn.close()
    today = date.today()
    by_day = {}
    for r in rows:
        d = _task_row_to_dict(r, today)
        day = int(d["due_date"][8:10])
        by_day.setdefault(day, []).append(d)
    return by_day


# ---- Планировщик (дневной / недельный) ----

DEFAULT_SLOTS = [f"{h:02d}:00" for h in list(range(6, 24)) + list(range(0, 2))]


def get_schedule(iso_date):
    conn = get_db()
    rows = conn.execute("SELECT * FROM schedule_entries WHERE date=?", (iso_date,)).fetchall()
    conn.close()
    by_slot = {r["time_label"]: dict(r) for r in rows}
    result = []
    for slot in DEFAULT_SLOTS:
        e = by_slot.get(slot)
        result.append({"time": slot, "task_id": e["task_id"] if e else None,
                        "note": e["note"] if e else ""})
    return result


def set_schedule_entry(iso_date, time_label, task_id, note):
    conn = get_db()
    existing = conn.execute("SELECT id FROM schedule_entries WHERE date=? AND time_label=?",
                             (iso_date, time_label)).fetchone()
    if not task_id and not note:
        if existing:
            conn.execute("DELETE FROM schedule_entries WHERE id=?", (existing["id"],))
    elif existing:
        conn.execute("UPDATE schedule_entries SET task_id=?, note=? WHERE id=?",
                     (task_id or None, note, existing["id"]))
    else:
        conn.execute("INSERT INTO schedule_entries (date, time_label, task_id, note) VALUES (?,?,?,?)",
                     (iso_date, time_label, task_id or None, note))
    conn.commit()
    conn.close()
