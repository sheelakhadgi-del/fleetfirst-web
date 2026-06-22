"""
Depreciation schedule logic for FleetFirst.

Policy:
- Life: 60 months for all trucks
- Residual: $5,000 most trucks; $15,000 for J100031/J100040/J100045; $51,580 for Ryder/1950
- Acq date <= 15th → full month in acquisition month
- Acq date >  15th → depreciation starts following month
- Month of repo is NOT depreciated
- Re-seated trucks start a NEW 60-month period at the new cost basis
"""
from datetime import date
from dateutil.relativedelta import relativedelta


def depr_start_month(acq_date):
    """First month that gets a depreciation charge (date = 1st of that month)."""
    if acq_date.day <= 15:
        return acq_date.replace(day=1)
    return (acq_date.replace(day=1) + relativedelta(months=1))


def months_of_depr(start_date, as_of_date):
    """
    Count months of depreciation from start_date through as_of_date (inclusive).
    as_of_date is treated as the last day of the month you want to include.
    """
    first_month = depr_start_month(start_date)
    last_month = as_of_date.replace(day=1) + relativedelta(months=1)  # month AFTER as_of
    if last_month <= first_month:
        return 0
    delta = relativedelta(last_month, first_month)
    return delta.years * 12 + delta.months


def monthly_depr_amount(cost_basis, residual_value, life_months=60):
    return round((float(cost_basis) - float(residual_value)) / life_months, 2)


def accumulated_depr_at(period, as_of_date):
    """Accumulated depreciation for one DepreciationPeriod through as_of_date."""
    monthly = monthly_depr_amount(period.cost_basis, period.residual_value, period.life_months)
    # Cap at end_date if the period was closed before as_of_date
    effective_end = period.end_date if (period.end_date and period.end_date < as_of_date) else as_of_date
    months = months_of_depr(period.start_date, effective_end)
    max_months = period.life_months
    months = min(months, max_months)
    return round(monthly * months, 2)


def book_value_at(periods, acq_cost, residual_value, as_of_date):
    """
    Net book value of a truck at as_of_date.
    Sums accumulated depreciation across all active-or-past periods.
    Falls back to acquisition_cost / residual_value if no periods exist.
    """
    if not periods:
        return float(acq_cost)
    total_accum = sum(accumulated_depr_at(p, as_of_date) for p in periods)
    bv = float(acq_cost) - total_accum
    return max(bv, float(residual_value))


def monthly_depr_for_month(period, year, month):
    """Return the depreciation charge for one period in a specific (year, month).
    Returns 0 if the period is not active that month."""
    first = date(year, month, 1)
    start = depr_start_month(period.start_date)
    if first < start:
        return 0.0
    if period.end_date and first >= period.end_date.replace(day=1):
        return 0.0
    months_elapsed = months_of_depr(period.start_date, first)
    if months_elapsed > period.life_months:
        return 0.0
    return monthly_depr_amount(period.cost_basis, period.residual_value, period.life_months)


def build_month_list(start_year, start_month, end_year, end_month):
    """Return list of (year, month) tuples from start through end inclusive."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def truck_schedule_row(truck, as_of_date=None):
    """
    Build one row for the depreciation schedule table.
    Returns dict with truck info and month-by-month accumulated depreciation.
    """
    if as_of_date is None:
        as_of_date = date.today()

    periods = sorted(truck.depreciation_periods, key=lambda p: p.start_date)
    if not periods:
        return None

    # Use earliest period start as schedule start
    start = periods[0].start_date

    months = build_month_list(start.year, start.month, as_of_date.year, as_of_date.month)
    monthly_amounts = {}
    for y, m in months:
        monthly_amounts[(y, m)] = sum(monthly_depr_for_month(p, y, m) for p in periods)

    # Current period stats
    active = next((p for p in reversed(periods) if not p.end_date), periods[-1])
    monthly = monthly_depr_amount(active.cost_basis, active.residual_value, active.life_months)
    total_accum = sum(accumulated_depr_at(p, as_of_date) for p in periods)
    bv = max(float(active.cost_basis) - total_accum, float(active.residual_value))

    return {
        "truck": truck,
        "periods": periods,
        "monthly_depreciation": monthly,
        "accumulated_depreciation": round(total_accum, 2),
        "book_value": round(bv, 2),
        "monthly_amounts": monthly_amounts,
    }


def depreciation_schedule(trucks, as_of_date=None):
    """
    Generate the full depreciation schedule across all trucks.
    Returns: {
        "months": [(y, m), ...],
        "rows_1504": [...],
        "rows_1950": [...],
        "totals": {"monthly": x, "accumulated": x, "book_value": x, "by_month": {(y,m): x}},
    }
    """
    if as_of_date is None:
        as_of_date = date.today()

    all_periods = []
    for t in trucks:
        all_periods.extend(t.depreciation_periods)

    if not all_periods:
        return {"months": [], "rows_1504": [], "rows_1950": [], "totals": {}}

    earliest = min(p.start_date for p in all_periods)
    months = build_month_list(earliest.year, earliest.month, as_of_date.year, as_of_date.month)

    rows_1504 = []
    rows_1950 = []
    for t in sorted(trucks, key=lambda x: (x.asset_account or "1504", x.truck_id or x.vin)):
        row = truck_schedule_row(t, as_of_date)
        if row is None:
            continue
        # Expand row's monthly_amounts to cover ALL months in the full schedule
        expanded = {}
        for ym in months:
            expanded[ym] = row["monthly_amounts"].get(ym, 0.0)
        row["monthly_amounts"] = expanded
        if (t.asset_account or "1504") == "1950":
            rows_1950.append(row)
        else:
            rows_1504.append(row)

    all_rows = rows_1504 + rows_1950
    total_monthly = round(sum(r["monthly_depreciation"] for r in all_rows), 2)
    total_accum = round(sum(r["accumulated_depreciation"] for r in all_rows), 2)
    total_bv = round(sum(r["book_value"] for r in all_rows), 2)
    by_month = {}
    for ym in months:
        by_month[ym] = round(sum(r["monthly_amounts"].get(ym, 0) for r in all_rows), 2)

    return {
        "months": months,
        "rows_1504": rows_1504,
        "rows_1950": rows_1950,
        "totals": {
            "monthly": total_monthly,
            "accumulated": total_accum,
            "book_value": total_bv,
            "by_month": by_month,
        },
    }
