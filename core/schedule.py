"""
Amortization schedule calculator — shared core logic.
"""
from datetime import datetime, timedelta
from decimal import Decimal


def _parse(d):
    if isinstance(d, datetime):
        return d
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d/%Y", "%-m/%-d/%y"):
        try:
            return datetime.strptime(str(d).strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {d}")


def build_schedule(lease_start, term_weeks, initial_balance, weekly_payment, annual_rate):
    """
    Returns list of week dicts: week, start_date, end_date, principal, interest, balance.
    Skip weeks (5th occurrence of weekday in month) are excluded.
    """
    weekly_rate = float(annual_rate) / 52
    balance = float(initial_balance)
    start = _parse(lease_start)
    schedule = []
    week_num = 0
    current = start

    while week_num < int(term_weeks) and balance > 0.005:
        day_of_week = current.weekday()
        first_same = current.replace(day=1)
        while first_same.weekday() != day_of_week:
            first_same += timedelta(days=1)
        occurrence = (current.day - first_same.day) // 7 + 1
        is_skip = (occurrence == 5)

        if not is_skip:
            interest = round(balance * weekly_rate, 2)
            principal = min(round(float(weekly_payment) - interest, 2), balance)
            balance = round(balance - principal, 2)
            schedule.append({
                "week": week_num + 1,
                "start_date": current,
                "end_date": current + timedelta(days=6),
                "principal": principal,
                "interest": interest,
                "balance": balance,
            })
            week_num += 1

        current += timedelta(days=7)

    return schedule


def get_week_for_date(schedule, payment_date):
    pd = _parse(payment_date)
    best = None
    for entry in schedule:
        if entry["start_date"] <= pd <= entry["end_date"]:
            return entry
        if entry["start_date"] <= pd:
            best = entry
    return best


def split_payment(amount, schedule_entry):
    p = schedule_entry["principal"]
    i = schedule_entry["interest"]
    total = p + i
    if total == 0:
        return float(amount), 0.0
    p_pct = p / total
    principal = round(float(amount) * p_pct, 2)
    interest = round(float(amount) - principal, 2)
    return principal, interest


def current_balance(schedule, as_of_date):
    """Return the running balance as of a given date."""
    balance = None
    pd = _parse(as_of_date)
    for entry in schedule:
        if entry["start_date"] <= pd:
            balance = entry["balance"]
        else:
            break
    return balance


def current_interest_accrued(schedule, lease_start, as_of_date, annual_rate, initial_balance):
    """
    Approximate interest receivable accrued but not yet paid as of date.
    Simplified: uses last schedule entry's weekly interest pro-rated.
    """
    entry = get_week_for_date(schedule, as_of_date)
    if not entry:
        return 0.0
    bal = entry["balance"] + entry["principal"]
    days_in_week = (_parse(as_of_date) - entry["start_date"]).days
    daily_rate = float(annual_rate) / 365
    return round(bal * daily_rate * days_in_week, 2)
