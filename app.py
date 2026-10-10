from datetime import date, timedelta
import calendar
import hashlib
from functools import wraps
import csv
import io
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

import database as db

app = Flask(__name__)
# Ключ лучше задать переменной окружения SECRET_KEY на сервере
app.secret_key = os.environ.get('SECRET_KEY', 'ваш-секретный-ключ-замените-на-реальный-32-символа-минимум')

db.init_db(seed=True)
db.init_tasks_db()


def today_ym():
    t = date.today()
    return t.year, t.month


# ================================================================
# BEFORE REQUEST - ЛОГИРОВАНИЕ ПОСЕЩЕНИЙ
# ================================================================

@app.before_request
def log_visits():
    """Логирует все посещения страниц (кроме статики и страниц авторизации)."""
    # Пропускаем статические файлы и страницы авторизации
    if request.path.startswith('/static/') or request.path in ['/login', '/register']:
        return

    # Пропускаем AJAX-запросы
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return

    user_id = session.get('user_id')
    db.log_visit(
        user_id=user_id,
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        path=request.path
    )


# ================================================================
# АДМИН-МАРШРУТЫ
# ================================================================

def admin_required(f):
    """Декоратор для проверки прав администратора."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему')
            return redirect(url_for('login'))

        if not db.is_admin(session['user_id']):
            flash('Доступ запрещён. Только для администраторов.')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


@app.route('/admin')
@admin_required
def admin_panel():
    """Админ-панель."""
    stats = db.get_admin_stats()
    users = db.get_all_users()
    return render_template(
        'admin.html',
        stats=stats,
        users=users,
        active='admin'
    )


@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    """Детальная страница пользователя."""
    user_stats = db.get_user_stats(user_id)
    if not user_stats:
        flash('Пользователь не найден')
        return redirect(url_for('admin_panel'))

    return render_template(
        'admin_user.html',
        user=user_stats,
        active='admin'
    )


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    if 'user_id' in session:
        conn = db.get_db()
        user = conn.execute(
            "SELECT id, username, display_name, is_admin FROM users WHERE id = ?",
            (session['user_id'],)
        ).fetchone()
        conn.close()
        return dict(user) if user else None
    return None


@app.context_processor
def inject_now():
    y, m = today_ym()
    return {
        "now_y": y,
        "now_m": m,
        "date": date,
        "current_user": get_current_user()
    }


# ================================================================
# АВТОРИЗАЦИЯ
# ================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not display_name or not password:
            flash('Все поля обязательны для заполнения')
            return render_template('register.html')

        if password != confirm:
            flash('Пароли не совпадают')
            return render_template('register.html')

        if len(password) < 6:
            flash('Пароль должен быть не менее 6 символов')
            return render_template('register.html')

        conn = db.get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            conn.close()
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
            (username, display_name, password_hash)
        )
        conn.commit()
        conn.close()

        flash('Регистрация прошла успешно! Теперь войдите в систему')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Заполните все поля')
            return render_template('login.html')

        conn = db.get_db()
        user = conn.execute(
            "SELECT id, username, display_name, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        ok = False
        if user:
            stored = user["password_hash"] or ""
            if stored.startswith(("pbkdf2:", "scrypt:")):
                ok = check_password_hash(stored, password)
            else:
                # старые пароли (sha256 без соли): проверяем и сразу перехешируем
                ok = stored == hashlib.sha256(password.encode()).hexdigest()
                if ok:
                    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                                 (generate_password_hash(password), user["id"]))
                    conn.commit()
        conn.close()

        if ok:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            return redirect(url_for('index'))

        flash('Неверное имя пользователя или пароль')
        return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы')
    return redirect(url_for('login'))


# ================================================================
# ГЛАВНАЯ
# ================================================================

@app.route("/")
@login_required
def index():
    y, m = today_ym()
    return redirect(url_for("daily", year=y, month=m))


# ================================================================
# ДНЕВНЫЕ ПРИВЫЧКИ
# ================================================================

@app.route("/daily/<int:year>/<int:month>")
@login_required
def daily(year, month):
    user_id = session['user_id']
    habits, entries, ndays = db.get_daily_grid(user_id, year, month)
    stats = db.daily_stats(user_id, year, month)
    streaks = db.habit_streaks(user_id)
    t = date.today()
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    existing = {h["name"].lower() for h in habits}
    library = [(sphere, [n for n in names if n.lower() not in existing])
               for sphere, names in db.HABIT_LIBRARY]
    return render_template(
        "daily.html",
        habits=habits, entries=entries, ndays=ndays, stats=stats,
        streaks=streaks, library=[x for x in library if x[1]],
        best_streak=max([v["best"] for v in streaks.values()] or [0]),
        is_current_month=(year, month) == (t.year, t.month),
        year=year, month=month, month_name=db.MONTHS_RU[month],
        weekdays=db.WEEKDAYS_RU,
        today=(t.year, t.month, t.day),
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        active="daily",
    )


@app.route("/daily/toggle", methods=["POST"])
@login_required
def daily_toggle():
    user_id = session['user_id']
    data = request.get_json()
    done = db.toggle_daily_entry(
        user_id,
        int(data["habit_id"]),
        int(data["year"]),
        int(data["month"]),
        int(data["day"])
    )
    stats = db.daily_stats(user_id, int(data["year"]), int(data["month"]))
    return jsonify({"done": done, "stats": stats})


@app.route("/daily/set", methods=["POST"])
@login_required
def daily_set():
    """Ставит отметке состояние: 0 — пусто, 1 — выполнено, 2 — пропуск."""
    user_id = session['user_id']
    data = request.get_json()
    y, m = int(data["year"]), int(data["month"])
    state = db.set_daily_entry(user_id, int(data["habit_id"]), y, m, int(data["day"]), int(data["state"]))
    return jsonify({
        "state": state,
        "stats": db.daily_stats(user_id, y, m),
        "streaks": db.habit_streaks(user_id),
    })


@app.route("/daily/export.csv")
@login_required
def daily_export():
    """Резервная копия всех отметок ежедневных привычек в CSV (открывается в Excel)."""
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM, чтобы Excel понял кириллицу
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Дата", "Привычка", "Статус"])
    w.writerows(db.export_daily_rows(session['user_id']))
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=habits.csv"})


@app.route("/daily/add", methods=["POST"])
@login_required
def daily_add():
    user_id = session['user_id']
    name = request.form.get("name", "").strip()
    goal = request.form.get("goal", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_daily_habit(user_id, name, int(goal) if goal.isdigit() else None)
    return redirect(url_for("daily", year=year, month=month))


@app.route("/daily/delete/<int:habit_id>", methods=["POST"])
@login_required
def daily_delete(habit_id):
    user_id = session['user_id']
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_daily_habit(user_id, habit_id)
    return redirect(url_for("daily", year=year, month=month))


# ================================================================
# ЕЖЕНЕДЕЛЬНЫЕ ПРИВЫЧКИ
# ================================================================

@app.route("/weekly/<int:year>/<int:month>")
@login_required
def weekly(year, month):
    user_id = session['user_id']
    habits, entries, nweeks = db.get_weekly_grid(user_id, year, month)
    week = request.args.get("week", type=int) or 1
    week = max(1, min(week, nweeks))
    stats = db.weekly_stats(user_id, year, month, week)
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    return render_template(
        "weekly.html",
        habits=habits, entries=entries, nweeks=nweeks, stats=stats, week=week,
        year=year, month=month, month_name=db.MONTHS_RU[month],
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        active="weekly",
    )


@app.route("/weekly/toggle", methods=["POST"])
@login_required
def weekly_toggle():
    user_id = session['user_id']
    data = request.get_json()
    done = db.toggle_weekly_entry(
        user_id,
        int(data["habit_id"]),
        int(data["year"]),
        int(data["month"]),
        int(data["week"])
    )
    stats = db.weekly_stats(
        user_id,
        int(data["year"]),
        int(data["month"]),
        int(data["week"])
    )
    return jsonify({"done": done, "stats": stats})


@app.route("/weekly/add", methods=["POST"])
@login_required
def weekly_add():
    user_id = session['user_id']
    name = request.form.get("name", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_weekly_habit(user_id, name)
    return redirect(url_for("weekly", year=year, month=month))


@app.route("/weekly/delete/<int:habit_id>", methods=["POST"])
@login_required
def weekly_delete(habit_id):
    user_id = session['user_id']
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_weekly_habit(user_id, habit_id)
    return redirect(url_for("weekly", year=year, month=month))


# ================================================================
# ЕЖЕМЕСЯЧНЫЕ ПРИВЫЧКИ
# ================================================================

@app.route("/monthly/<int:year>/<int:month>")
@login_required
def monthly(year, month):
    user_id = session['user_id']
    habits, entries = db.get_monthly_list(user_id, year, month)
    stats = db.monthly_stats(user_id, year, month)
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    return render_template(
        "monthly.html",
        habits=habits, entries=entries, stats=stats,
        year=year, month=month, month_name=db.MONTHS_RU[month],
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        active="monthly",
    )


@app.route("/monthly/toggle", methods=["POST"])
@login_required
def monthly_toggle():
    user_id = session['user_id']
    data = request.get_json()
    done = db.toggle_monthly_entry(
        user_id,
        int(data["habit_id"]),
        int(data["year"]),
        int(data["month"])
    )
    stats = db.monthly_stats(user_id, int(data["year"]), int(data["month"]))
    return jsonify({"done": done, "stats": stats})


@app.route("/monthly/add", methods=["POST"])
@login_required
def monthly_add():
    user_id = session['user_id']
    name = request.form.get("name", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_monthly_habit(user_id, name)
    return redirect(url_for("monthly", year=year, month=month))


@app.route("/monthly/delete/<int:habit_id>", methods=["POST"])
@login_required
def monthly_delete(habit_id):
    user_id = session['user_id']
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_monthly_habit(user_id, habit_id)
    return redirect(url_for("monthly", year=year, month=month))


# ================================================================
# ЦЕЛИ
# ================================================================

@app.route("/goals")
@login_required
def goals():
    user_id = session['user_id']
    goal_list, spheres, done_total, total, overall_pct = db.get_goals(user_id)
    return render_template(
        "goals.html", goals=goal_list, spheres=spheres,
        done_total=done_total, total=total, overall_pct=overall_pct,
        active="goals",
    )


@app.route("/goals/add", methods=["POST"])
@login_required
def goals_add():
    user_id = session['user_id']
    db.add_goal(
        user_id,
        request.form.get("title", ""),
        request.form.get("sphere", ""),
        request.form.get("reward", ""),
        request.form.get("deadline", "")
    )
    return redirect(url_for("goals"))


@app.route("/goals/delete/<int:goal_id>", methods=["POST"])
@login_required
def goals_delete(goal_id):
    user_id = session['user_id']
    db.delete_goal(user_id, goal_id)
    return redirect(url_for("goals"))


@app.route("/goals/status/<int:goal_id>", methods=["POST"])
@login_required
def goals_status(goal_id):
    user_id = session['user_id']
    status = request.form.get("status", "in_progress")
    db.set_goal_status(user_id, goal_id, status)
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/step/add", methods=["POST"])
@login_required
def goals_step_add(goal_id):
    user_id = session['user_id']
    text = request.form.get("text", "")
    if text.strip():
        db.add_goal_step(user_id, goal_id, text)
    return redirect(url_for("goals"))


@app.route("/goals/step/toggle", methods=["POST"])
@login_required
def goals_step_toggle():
    user_id = session['user_id']
    data = request.get_json()
    done = db.toggle_goal_step(user_id, int(data["step_id"]))
    goal_list, spheres, done_total, total, overall_pct = db.get_goals(user_id)
    return jsonify({
        "done": done,
        "done_total": done_total,
        "total": total,
        "overall_pct": overall_pct
    })


# ================================================================
# ТРЕКЕР ЗАДАЧ
# ================================================================

@app.route("/tasks")
@login_required
def tasks_list():
    user_id = session['user_id']
    status = request.args.get("status") or None
    priority = request.args.get("priority") or None
    assignee = request.args.get("assignee") or None
    category = request.args.get("category") or None
    q = request.args.get("q") or None
    tasks = db.get_tasks(
        user_id,
        status=status,
        priority=priority,
        assignee=assignee,
        category=category,
        q=q
    )
    stats = db.task_stats(user_id)
    return render_template(
        "tasks_list.html", tasks=tasks, stats=stats,
        statuses=db.STATUSES, priorities=db.PRIORITIES,
        assignees=db.distinct_values(user_id, "assignee"),
        categories=db.distinct_values(user_id, "category"),
        f_status=status, f_priority=priority,
        f_assignee=assignee, f_category=category, f_q=q or "",
        active="tasks", tasks_tab="list",
    )


@app.route("/tasks/add", methods=["POST"])
@login_required
def tasks_add():
    user_id = session['user_id']
    f = request.form
    db.add_task(
        user_id,
        f.get("title", ""),
        f.get("due_date", ""),
        f.get("assignee", ""),
        f.get("status", "Не начато"),
        f.get("category", ""),
        f.get("priority", "Средний"),
        f.get("important") == "on",
        f.get("urgent") == "on",
        f.get("description", ""),
    )
    return redirect(request.referrer or url_for("tasks_list"))


@app.route("/tasks/update/<int:task_id>", methods=["POST"])
@login_required
def tasks_update(task_id):
    user_id = session['user_id']
    f = request.form
    fields = {}
    for key in ("title", "due_date", "assignee", "status", "category", "priority", "description"):
        if key in f:
            fields[key] = f.get(key)
    if "important" in f:
        fields["important"] = int(f.get("important") == "on")
    if "urgent" in f:
        fields["urgent"] = int(f.get("urgent") == "on")
    db.update_task(user_id, task_id, **fields)
    return redirect(request.referrer or url_for("tasks_list"))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
@login_required
def tasks_delete(task_id):
    user_id = session['user_id']
    db.delete_task(user_id, task_id)
    return redirect(request.referrer or url_for("tasks_list"))


@app.route("/tasks/status/<int:task_id>", methods=["POST"])
@login_required
def tasks_status(task_id):
    user_id = session['user_id']
    data = request.get_json()
    db.update_task(user_id, task_id, status=data["status"])
    return jsonify({"ok": True, "stats": db.task_stats(user_id)})


@app.route("/tasks/field/<int:task_id>", methods=["POST"])
@login_required
def tasks_field(task_id):
    user_id = session['user_id']
    data = request.get_json()
    field, value = data["field"], data["value"]
    if field in ("important", "urgent"):
        value = int(bool(value))
    db.update_task(user_id, task_id, **{field: value})
    return jsonify({"ok": True})


@app.route("/tasks/kanban")
@login_required
def tasks_kanban():
    user_id = session['user_id']
    assignee = request.args.get("assignee") or None
    tasks = db.get_tasks(user_id, assignee=assignee)
    columns = {s: [t for t in tasks if t["status"] == s] for s in db.STATUSES}
    return render_template(
        "tasks_kanban.html", columns=columns, statuses=db.STATUSES,
        assignees=db.distinct_values(user_id, "assignee"), f_assignee=assignee,
        active="tasks", tasks_tab="kanban",
    )


@app.route("/tasks/matrix")
@login_required
def tasks_matrix():
    user_id = session['user_id']
    assignee = request.args.get("assignee") or None
    quads, pct = db.matrix_tasks(user_id, assignee=assignee)
    return render_template(
        "tasks_matrix.html", quads=quads, pct=pct,
        assignees=db.distinct_values(user_id, "assignee"), f_assignee=assignee,
        active="tasks", tasks_tab="matrix",
    )


@app.route("/tasks/calendar/<int:year>/<int:month>")
@login_required
def tasks_calendar(year, month):
    user_id = session['user_id']
    by_day = db.calendar_tasks(user_id, year, month)
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    t = date.today()
    return render_template(
        "tasks_calendar.html", weeks=weeks, by_day=by_day, year=year, month=month,
        month_name=db.MONTHS_RU[month],
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        today=(t.year, t.month, t.day),
        active="tasks", tasks_tab="calendar",
    )


@app.route("/tasks/planner/daily")
@app.route("/tasks/planner/daily/<iso_date>")
@login_required
def tasks_planner_daily(iso_date=None):
    user_id = session['user_id']
    d = date.fromisoformat(iso_date) if iso_date else date.today()
    schedule = db.get_schedule(user_id, d.isoformat())
    open_tasks = db.get_tasks(user_id)
    open_tasks = [t for t in open_tasks if t["status"] != "Выполнено"]
    prio_order = {"Критичный": 0, "Высокий": 1, "Средний": 2, "Низкий": 3}
    top3 = sorted(open_tasks, key=lambda t: prio_order.get(t["priority"], 9))[:3]
    upcoming = sorted(
        [t for t in db.get_tasks(user_id) if t["due_date"] and t["status"] != "Выполнено"],
        key=lambda t: t["due_date"]
    )[:8]
    return render_template(
        "tasks_planner.html", mode="daily", the_date=d, schedule=schedule,
        open_tasks=open_tasks, upcoming=upcoming, top3=top3,
        prev_date=(d - timedelta(days=1)).isoformat(),
        next_date=(d + timedelta(days=1)).isoformat(),
        active="tasks", tasks_tab="daily",
    )


@app.route("/tasks/planner/weekly")
@app.route("/tasks/planner/weekly/<iso_date>")
@login_required
def tasks_planner_weekly(iso_date=None):
    user_id = session['user_id']
    start = date.fromisoformat(iso_date) if iso_date else date.today()
    start = start - timedelta(days=start.weekday())
    days = [start + timedelta(days=i) for i in range(7)]
    week_schedule = {d.isoformat(): db.get_schedule(user_id, d.isoformat()) for d in days}
    open_tasks = [t for t in db.get_tasks(user_id) if t["status"] != "Выполнено"]
    return render_template(
        "tasks_planner.html", mode="weekly", days=days, week_schedule=week_schedule,
        open_tasks=open_tasks, the_date=start,
        prev_date=(start - timedelta(days=7)).isoformat(),
        next_date=(start + timedelta(days=7)).isoformat(),
        active="tasks", tasks_tab="weekly",
    )


@app.route("/tasks/planner/set", methods=["POST"])
@login_required
def tasks_planner_set():
    user_id = session['user_id']
    data = request.get_json()
    db.set_schedule_entry(
        user_id,
        data["date"],
        data["time"],
        data.get("task_id") or None,
        data.get("note", "")
    )
    return jsonify({"ok": True})


if __name__ == "__main__":
    # debug включается только явно: FLASK_DEBUG=1 python app.py
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=5000)