from datetime import date
from flask import Flask, render_template, request, redirect, url_for, jsonify

import database as db

app = Flask(__name__)
db.init_db(seed=True)


def today_ym():
    t = date.today()
    return t.year, t.month


@app.context_processor
def inject_now():
    y, m = today_ym()
    return {"now_y": y, "now_m": m, "date": date}


# ---------------------------------------------------------------- ГЛАВНАЯ
@app.route("/")
def index():
    y, m = today_ym()
    return redirect(url_for("daily", year=y, month=m))


# ---------------------------------------------------------------- ДНЕВНЫЕ
@app.route("/daily/<int:year>/<int:month>")
def daily(year, month):
    habits, entries, ndays = db.get_daily_grid(year, month)
    stats = db.daily_stats(year, month)
    t = date.today()
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    return render_template(
        "daily.html",
        habits=habits, entries=entries, ndays=ndays, stats=stats,
        year=year, month=month, month_name=db.MONTHS_RU[month],
        weekdays=db.WEEKDAYS_RU,
        today=(t.year, t.month, t.day),
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        active="daily",
    )


@app.route("/daily/toggle", methods=["POST"])
def daily_toggle():
    data = request.get_json()
    done = db.toggle_daily_entry(int(data["habit_id"]), int(data["year"]),
                                  int(data["month"]), int(data["day"]))
    stats = db.daily_stats(int(data["year"]), int(data["month"]))
    return jsonify({"done": done, "stats": stats})


@app.route("/daily/add", methods=["POST"])
def daily_add():
    name = request.form.get("name", "").strip()
    goal = request.form.get("goal", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_daily_habit(name, int(goal) if goal.isdigit() else None)
    return redirect(url_for("daily", year=year, month=month))


@app.route("/daily/delete/<int:habit_id>", methods=["POST"])
def daily_delete(habit_id):
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_daily_habit(habit_id)
    return redirect(url_for("daily", year=year, month=month))


# ---------------------------------------------------------------- ЕЖЕНЕДЕЛЬНЫЕ
@app.route("/weekly/<int:year>/<int:month>")
def weekly(year, month):
    habits, entries, nweeks = db.get_weekly_grid(year, month)
    week = request.args.get("week", type=int) or 1
    week = max(1, min(week, nweeks))
    stats = db.weekly_stats(year, month, week)
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
def weekly_toggle():
    data = request.get_json()
    done = db.toggle_weekly_entry(int(data["habit_id"]), int(data["year"]),
                                   int(data["month"]), int(data["week"]))
    stats = db.weekly_stats(int(data["year"]), int(data["month"]), int(data["week"]))
    return jsonify({"done": done, "stats": stats})


@app.route("/weekly/add", methods=["POST"])
def weekly_add():
    name = request.form.get("name", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_weekly_habit(name)
    return redirect(url_for("weekly", year=year, month=month))


@app.route("/weekly/delete/<int:habit_id>", methods=["POST"])
def weekly_delete(habit_id):
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_weekly_habit(habit_id)
    return redirect(url_for("weekly", year=year, month=month))


# ---------------------------------------------------------------- ЕЖЕМЕСЯЧНЫЕ
@app.route("/monthly/<int:year>/<int:month>")
def monthly(year, month):
    habits, entries = db.get_monthly_list(year, month)
    stats = db.monthly_stats(year, month)
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
def monthly_toggle():
    data = request.get_json()
    done = db.toggle_monthly_entry(int(data["habit_id"]), int(data["year"]), int(data["month"]))
    stats = db.monthly_stats(int(data["year"]), int(data["month"]))
    return jsonify({"done": done, "stats": stats})


@app.route("/monthly/add", methods=["POST"])
def monthly_add():
    name = request.form.get("name", "").strip()
    year = request.form.get("year")
    month = request.form.get("month")
    if name:
        db.add_monthly_habit(name)
    return redirect(url_for("monthly", year=year, month=month))


@app.route("/monthly/delete/<int:habit_id>", methods=["POST"])
def monthly_delete(habit_id):
    year = request.form.get("year")
    month = request.form.get("month")
    db.delete_monthly_habit(habit_id)
    return redirect(url_for("monthly", year=year, month=month))


# ---------------------------------------------------------------- ЦЕЛИ
@app.route("/goals")
def goals():
    goal_list, spheres, done_total, total, overall_pct = db.get_goals()
    return render_template(
        "goals.html", goals=goal_list, spheres=spheres,
        done_total=done_total, total=total, overall_pct=overall_pct,
        active="goals",
    )


@app.route("/goals/add", methods=["POST"])
def goals_add():
    db.add_goal(request.form.get("title", ""), request.form.get("sphere", ""),
                request.form.get("reward", ""), request.form.get("deadline", ""))
    return redirect(url_for("goals"))


@app.route("/goals/delete/<int:goal_id>", methods=["POST"])
def goals_delete(goal_id):
    db.delete_goal(goal_id)
    return redirect(url_for("goals"))


@app.route("/goals/status/<int:goal_id>", methods=["POST"])
def goals_status(goal_id):
    status = request.form.get("status", "in_progress")
    db.set_goal_status(goal_id, status)
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/step/add", methods=["POST"])
def goals_step_add(goal_id):
    text = request.form.get("text", "")
    if text.strip():
        db.add_goal_step(goal_id, text)
    return redirect(url_for("goals"))


@app.route("/goals/step/toggle", methods=["POST"])
def goals_step_toggle():
    data = request.get_json()
    done = db.toggle_goal_step(int(data["step_id"]))
    goal_list, spheres, done_total, total, overall_pct = db.get_goals()
    return jsonify({"done": done, "done_total": done_total, "total": total, "overall_pct": overall_pct})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
