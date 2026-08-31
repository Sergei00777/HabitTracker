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
