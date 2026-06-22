import io
import csv
from datetime import date, datetime
from calendar import monthrange
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from .models import db, Truck, DepreciationPeriod
from core.depreciation import (depreciation_schedule, truck_schedule_row,
                                build_month_list, monthly_depr_for_month)

depr_bp = Blueprint("depreciation", __name__, url_prefix="/depreciation")


@depr_bp.route("/")
@login_required
def index():
    as_of_str = request.args.get("as_of", "")
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        as_of = date.today()

    trucks = Truck.query.filter(
        Truck.depreciation_periods.any()
    ).all()

    schedule = depreciation_schedule(trucks, as_of)
    return render_template("depreciation/index.html", schedule=schedule, as_of=as_of)


@depr_bp.route("/export")
@login_required
def export_csv():
    as_of_str = request.args.get("as_of", "")
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        as_of = date.today()

    trucks = Truck.query.filter(Truck.depreciation_periods.any()).all()
    schedule = depreciation_schedule(trucks, as_of)
    months = schedule["months"]

    buf = io.StringIO()
    w = csv.writer(buf)

    month_headers = [f"{m[0]}-{m[1]:02d}" for m in months]
    w.writerow(["Asset Account", "Truck ID", "VIN", "Description",
                "Acq Date", "Cost Basis", "Residual", "Life", "Monthly Depr",
                *month_headers, "Accum Depr", "Book Value"])

    for section_label, rows in [("1504 Fixed Assets", schedule["rows_1504"]),
                                  ("1950 Right of Use Assets", schedule["rows_1950"])]:
        for row in rows:
            t = row["truck"]
            p = row["periods"][0]
            monthly_cols = [f"{row['monthly_amounts'].get(m, 0):.2f}" for m in months]
            w.writerow([
                section_label, t.truck_id or "", t.vin, t.description or "",
                p.start_date.strftime("%m/%d/%Y"),
                f"{float(p.cost_basis):.2f}",
                f"{float(p.residual_value):.2f}",
                p.life_months,
                f"{row['monthly_depreciation']:.2f}",
                *monthly_cols,
                f"{row['accumulated_depreciation']:.2f}",
                f"{row['book_value']:.2f}",
            ])

    totals = schedule["totals"]
    total_monthly_cols = [f"{totals['by_month'].get(m, 0):.2f}" for m in months]
    w.writerow(["TOTAL", "", "", "", "", "", "", "", f"{totals['monthly']:.2f}",
                *total_monthly_cols, f"{totals['accumulated']:.2f}", f"{totals['book_value']:.2f}"])

    buf.seek(0)
    filename = f"depreciation_schedule_{as_of.strftime('%Y%m%d')}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@depr_bp.route("/export_je")
@login_required
def export_je():
    """Export a QBO-ready journal entry CSV for one month's depreciation."""
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))

    last_day = monthrange(year, month)[1]
    je_date_obj = date(year, month, last_day)
    je_date  = je_date_obj.strftime("%m/%d/%Y")
    # Date suffix used in journal no: MMDDYY
    date_suffix = je_date_obj.strftime("%m%d%y")
    memo_prefix = f"{date(year, month, 1).strftime('%B %Y')} Depreciation"

    trucks = Truck.query.filter(Truck.depreciation_periods.any()).order_by(
        Truck.asset_account, Truck.truck_id).all()

    # Build per-truck rows: (truck_id_label, lessee_name, amount)
    entries = []
    for truck in trucks:
        amount = round(sum(
            monthly_depr_for_month(p, year, month)
            for p in truck.depreciation_periods
        ), 2)
        if amount <= 0:
            continue
        label = truck.truck_id or truck.vin
        lease = truck.active_lease
        lessee = (lease.team_name or lease.driver_name or "") if lease else ""
        entries.append((label, lessee, amount))

    grand_total = round(sum(e[2] for e in entries), 2)

    if grand_total == 0:
        flash(f"No depreciation to export for {date(year, month, 1).strftime('%B %Y')}.", "warning")
        return redirect(url_for("depreciation.index"))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Transaction Date", "Transaction Type", "Journal No",
                "Name", "Memo/Description", "Account", "Debit", "Credit"])

    # ── One journal entry per truck ──────────────────────────────────────────
    # Each JE has two lines: debit 9110 Depreciation, credit 1604 Auto & Trucks A/D
    for label, lessee, amount in entries:
        je_no = f"{label} Depr{date_suffix}"
        memo  = f"{memo_prefix} - {label}"
        # Debit line
        w.writerow([je_date, "Journal Entry", je_no, lessee, memo,
                    "9110 Depreciation", f"{amount:.2f}", ""])
        # Credit line
        w.writerow([je_date, "Journal Entry", je_no, lessee, memo,
                    "1604 Auto & Trucks A/D", "", f"{amount:.2f}"])

    buf.seek(0)
    filename = f"depreciation_JE_{year}{month:02d}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@depr_bp.route("/truck/<int:truck_id>")
@login_required
def truck_detail(truck_id):
    truck = Truck.query.get_or_404(truck_id)
    as_of_str = request.args.get("as_of", "")
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        as_of = date.today()
    row = truck_schedule_row(truck, as_of)
    return render_template("depreciation/truck_detail.html", truck=truck, row=row, as_of=as_of)


@depr_bp.route("/truck/<int:truck_id>/add_period", methods=["GET", "POST"])
@login_required
def add_period(truck_id):
    truck = Truck.query.get_or_404(truck_id)
    if request.method == "POST":
        try:
            start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            cost_basis = float(request.form["cost_basis"])
            residual_value = float(request.form.get("residual_value", 5000))
            life_months = int(request.form.get("life_months", 60))
            notes = request.form.get("notes", "")
            end_date_str = request.form.get("end_date", "")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

            period = DepreciationPeriod(
                truck_id=truck_id,
                start_date=start_date,
                end_date=end_date,
                cost_basis=cost_basis,
                residual_value=residual_value,
                life_months=life_months,
                notes=notes,
            )
            db.session.add(period)
            db.session.commit()
            flash(f"Depreciation period added for {truck.truck_id or truck.vin}.", "success")
            return redirect(url_for("depreciation.truck_detail", truck_id=truck_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding period: {e}", "danger")

    return render_template("depreciation/add_period.html", truck=truck)


@depr_bp.route("/period/<int:period_id>/edit", methods=["GET", "POST"])
@login_required
def edit_period(period_id):
    period = DepreciationPeriod.query.get_or_404(period_id)
    truck = period.truck
    if request.method == "POST":
        try:
            period.start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            period.cost_basis = float(request.form["cost_basis"])
            period.residual_value = float(request.form.get("residual_value", 5000))
            period.life_months = int(request.form.get("life_months", 60))
            period.notes = request.form.get("notes", "")
            end_date_str = request.form.get("end_date", "")
            period.end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
            db.session.commit()
            flash("Depreciation period updated.", "success")
            return redirect(url_for("depreciation.truck_detail", truck_id=truck.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

    return render_template("depreciation/edit_period.html", period=period, truck=truck)


@depr_bp.route("/period/<int:period_id>/delete", methods=["POST"])
@login_required
def delete_period(period_id):
    period = DepreciationPeriod.query.get_or_404(period_id)
    truck_id = period.truck_id
    db.session.delete(period)
    db.session.commit()
    flash("Depreciation period deleted.", "warning")
    return redirect(url_for("depreciation.truck_detail", truck_id=truck_id))
