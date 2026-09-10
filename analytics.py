"""
analytics.py — Income pattern detection for IncomeRhythm.
Pure Python + standard library only (no extra deps beyond what's in requirements).
"""

from datetime import date, timedelta
from collections import defaultdict
from typing import Optional
import statistics

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------------------------------------------------------------------------
# Core aggregation helpers
# ---------------------------------------------------------------------------

def daily_totals(income_rows: list) -> dict:
    """
    Returns {date_str: total_amount} over all logged income.
    """
    totals: dict = defaultdict(float)
    for row in income_rows:
        totals[row["entry_date"]] += row["amount"]
    return dict(totals)


def daily_totals_by_source(income_rows: list) -> dict:
    """
    Returns {date_str: {source: amount}} for stacked charting.
    """
    result: dict = defaultdict(lambda: defaultdict(float))
    for row in income_rows:
        result[row["entry_date"]][row["source"]] += row["amount"]
    return {d: dict(s) for d, s in result.items()}


def source_totals(income_rows: list) -> dict:
    """Returns {source: total_amount}."""
    totals: dict = defaultdict(float)
    for row in income_rows:
        totals[row["source"]] += row["amount"]
    return dict(totals)


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def compute_analytics(income_rows: list) -> dict:
    """
    Returns a dict with:
      avg_daily_income, volatility_label, volatility_pct,
      lean_weekdays (list of 0-6 ints), lean_weekdays_names,
      best_weekday, best_weekday_name,
      total_30d, total_7d, days_with_income,
      today_income
    """
    if not income_rows:
        return _empty_analytics()

    totals = daily_totals(income_rows)

    # Filter to last 30 days for pattern stats
    cutoff_30 = (date.today() - timedelta(days=30)).isoformat()
    cutoff_7 = (date.today() - timedelta(days=7)).isoformat()

    amounts_30d = [v for k, v in totals.items() if k >= cutoff_30]
    amounts_7d = [v for k, v in totals.items() if k >= cutoff_7]

    total_30d = sum(amounts_30d)
    total_7d = sum(amounts_7d)

    avg_daily = statistics.mean(amounts_30d) if amounts_30d else 0.0

    # Volatility: coefficient of variation
    if len(amounts_30d) >= 2:
        std = statistics.stdev(amounts_30d)
        cv = (std / avg_daily * 100) if avg_daily > 0 else 0
    else:
        cv = 0

    if cv < 25:
        volatility_label = "stable"
    elif cv < 55:
        volatility_label = "moderate"
    else:
        volatility_label = "high"

    # Weekday averages
    weekday_sums: dict = defaultdict(float)
    weekday_counts: dict = defaultdict(int)
    for date_str, amount in totals.items():
        if date_str >= cutoff_30:
            try:
                d = date.fromisoformat(date_str)
                wd = d.weekday()
                weekday_sums[wd] += amount
                weekday_counts[wd] += 1
            except ValueError:
                pass

    weekday_avgs = {
        wd: weekday_sums[wd] / weekday_counts[wd]
        for wd in weekday_sums
        if weekday_counts[wd] > 0
    }

    # Lean = weekdays with avg below 60% of overall avg_daily
    lean_threshold = avg_daily * 0.60
    lean_weekdays = [wd for wd, avg in weekday_avgs.items() if avg < lean_threshold]
    lean_weekdays_names = [DAY_NAMES[wd] for wd in sorted(lean_weekdays)]

    best_weekday = max(weekday_avgs, key=weekday_avgs.get) if weekday_avgs else None
    best_weekday_name = DAY_NAMES[best_weekday] if best_weekday is not None else "N/A"

    # Today's income
    today_str = date.today().isoformat()
    today_income = totals.get(today_str, 0.0)

    return {
        "avg_daily_income": round(avg_daily, 2),
        "volatility_label": volatility_label,
        "volatility_pct": round(cv, 1),
        "lean_weekdays": lean_weekdays,
        "lean_weekdays_names": lean_weekdays_names,
        "best_weekday": best_weekday,
        "best_weekday_name": best_weekday_name,
        "total_30d": round(total_30d, 2),
        "total_7d": round(total_7d, 2),
        "days_with_income": len(amounts_30d),
        "today_income": round(today_income, 2),
        "weekday_avgs": {DAY_NAMES[k]: round(v, 2) for k, v in weekday_avgs.items()},
    }


def _empty_analytics() -> dict:
    return {
        "avg_daily_income": 0.0,
        "volatility_label": "unknown",
        "volatility_pct": 0.0,
        "lean_weekdays": [],
        "lean_weekdays_names": [],
        "best_weekday": None,
        "best_weekday_name": "N/A",
        "total_30d": 0.0,
        "total_7d": 0.0,
        "days_with_income": 0,
        "today_income": 0.0,
        "weekday_avgs": {},
    }


# ---------------------------------------------------------------------------
# Lean-period prediction
# ---------------------------------------------------------------------------

def get_upcoming_lean_days(analytics: dict, lookahead: int = 3) -> list:
    """
    Returns a list of upcoming day names (within `lookahead` days) that are
    predicted lean, based on weekday patterns.
    """
    lean_wds = set(analytics.get("lean_weekdays", []))
    upcoming = []
    for i in range(1, lookahead + 1):
        d = date.today() + timedelta(days=i)
        if d.weekday() in lean_wds:
            upcoming.append(DAY_NAMES[d.weekday()])
    return upcoming


# ---------------------------------------------------------------------------
# Chart data helpers
# ---------------------------------------------------------------------------

def chart_daily_income(income_rows: list, days: int = 30) -> dict:
    """
    Returns {"dates": [...], "income": [...]} ordered oldest→newest,
    covering last `days` days (filling zeros for missing days).
    """
    totals = daily_totals(income_rows)
    today = date.today()
    dates = []
    incomes = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        dates.append(d.strftime("%b %d"))
        incomes.append(totals.get(d.isoformat(), 0.0))
    return {"dates": dates, "income": incomes}


def chart_expense_income(income_rows: list, expense_rows: list, days: int = 14) -> dict:
    """
    Returns {"dates": [...], "income": [...], "expenses": [...]}
    """
    income_totals = daily_totals(income_rows)
    expense_totals = daily_totals(expense_rows)
    today = date.today()
    dates, incomes, expenses = [], [], []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        dates.append(d.strftime("%b %d"))
        incomes.append(income_totals.get(d.isoformat(), 0.0))
        expenses.append(expense_totals.get(d.isoformat(), 0.0))
    return {"dates": dates, "income": incomes, "expenses": expenses}


def weekday_avg_chart(analytics: dict) -> dict:
    """Returns {"days": [...], "avg_income": [...]} ordered Mon→Sun."""
    avgs = analytics.get("weekday_avgs", {})
    days = []
    vals = []
    for name in DAY_NAMES:
        if name in avgs:
            days.append(name[:3])
            vals.append(avgs[name])
    return {"days": days, "avg_income": vals}
