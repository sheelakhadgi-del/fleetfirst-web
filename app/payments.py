import csv, io, os
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, send_file, Response)
from flask_login import login_required
from .models import db, Truck, Lease, Payment
from core.schedule import build_schedule, get_week_for_date, split_payment

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

ACCOUNTS = {
    "1800": "1800 Due from CloudTrucks",
    "1951": "1951 Lease Receivable",
    "4300": "4300 Interest Income - Leasing",
    "2603": "2603 Truck Maintenance Deposit - Leasing",
}

_schedule_cache = {}


def _get_schedule(lease):
    key = lease.id
    if key not in _schedule_cache:
        _schedule_cache[key] = build_schedule(
            lease.lease_start, lease.term_weeks,
            float(lease.initial_balance), float(lease.weekly_payment),
            float(lease.annual_rate)
        )
    return _schedule_cache[key]


def _parse_amount(s):
    return float(str(s).replace("$", "").replace(",", "").strip() or 0)


def _fmt_date(d):
    if isinstance(d, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(d, fmt).strftime("%m/%d/%Y")
            except ValueError:
                continue
        return d
    return d.strftime("%m/%d/%Y")


def _find_lease(vin, team_id):
    """Look up lease by VIN first, then team_id."""
    truck = None
    if vin and vin.upper() not in ("NOTHING TO FILL", ""):
        truck = Truck.query.filter_by(vin=vin.upper()).first()
    if truck:
        lease = next((l for l in truck.leases if l.status == "ACTIVE"), None)
        if lease:
            return lease
    if team_id:
        lease = Lease.query.filter_by(team_id=team_id, status="ACTIVE").first()
        return lease
    return None


def _already_processed(lease_id, pdate, amount):
    existing = Payment.query.filter_by(
        lease_id=lease_id, payment_date=pdate
    ).filter(Payment.amount == amount).first()
    return existing is not None


@payments_bp.route("/")
@login_required
def history():
    page = request.args.get("page", 1, type=int)
    vin_filter = request.args.get("vin", "").strip()
    program_filter = request.args.get("program", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    q = Payment.query.join(Lease).join(Truck).order_by(
        Payment.payment_date.desc(), Payment.created_at.desc()
    )
    if vin_filter:
        q = q.filter(Truck.vin.ilike(f"%{vin_filter}%"))
    if program_filter:
        q = q.filter(Payment.program == program_filter)
    if date_from:
        try:
            q = q.filter(Payment.payment_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Payment.payment_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    payments = q.paginate(page=page, per_page=50, error_out=False)
    return render_template("payments/history.html", payments=payments,
                           vin_filter=vin_filter, program_filter=program_filter,
                           date_from=date_from, date_to=date_to)


@payments_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.endswith(".csv"):
            flash("Please upload a CSV file.", "danger")
            return render_template("payments/upload.html")

        content = f.read().decode("utf-8-sig")
        filename = f.filename
        result = _process_looker_csv(content, filename)

        flash(
            f"Processed: {result['lease_payments']} lease payments, "
            f"{result['maint_payments']} maintenance payments, "
            f"{result['skipped']} skipped.",
            "success" if result["skipped"] == 0 else "warning"
        )
        if result["warnings"]:
            for w in result["warnings"][:10]:
                flash(w, "warning")

        # Store the QBO CSV in session for download
        if result["qbo_csv"]:
            from flask import session
            session["last_qbo_csv"] = result["qbo_csv"]
            session["last_qbo_filename"] = filename.replace(".csv", "_QBO_JE.csv")

        return redirect(url_for("payments.download_last"))

    return render_template("payments/upload.html")


@payments_bp.route("/download-last")
@login_required
def download_last():
    from flask import session
    qbo_csv = session.get("last_qbo_csv")
    filename = session.get("last_qbo_filename", "QBO_JE.csv")
    if not qbo_csv:
        flash("No file to download. Please upload a Looker CSV first.", "warning")
        return redirect(url_for("payments.upload"))
    return Response(
        qbo_csv,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _process_looker_csv(content, filename):
    reader = csv.DictReader(io.StringIO(content))
    rows = [r for r in reader if r.get("Payment Date", "").strip()]

    je_lines = []
    log_rows = []
    skipped = []
    warnings = []

    for row in rows:
        payment_date_str = row["Payment Date"].strip()
        team_name = row.get("Team Name", "").strip()
        team_id = row.get("Team ID", "").strip()
        program = row.get("Vendor Program", "").strip()
        vin = row.get("Subheader", "").strip()
        amount = _parse_amount(row.get("Payment Amount", 0))

        if amount == 0:
            continue

        lease = _find_lease(vin, team_id)
        if not lease:
            warnings.append(f"No lease for VIN={vin} / {team_name}")
            skipped.append(row)
            continue

        try:
            pdate = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                pdate = datetime.strptime(payment_date_str, "%m/%d/%Y").date()
            except ValueError:
                warnings.append(f"Bad date {payment_date_str}")
                skipped.append(row)
                continue

        if _already_processed(lease.id, pdate, amount):
            continue

        truck = lease.truck
        truck_id = truck.truck_id or lease.truck.vin[-6:]
        driver = lease.driver_name or team_name
        fmt_date = _fmt_date(pdate)
        date_sfx = pdate.strftime("%m%d%y")

        if program == "FLEET_FIRST_TRUCK_LEASE":
            sched = _get_schedule(lease)
            entry = get_week_for_date(sched, payment_date_str)
            if not entry:
                warnings.append(f"No schedule entry for {vin} on {payment_date_str}")
                principal, interest = amount, 0.0
            else:
                principal, interest = split_payment(amount, entry)

            je_ref = f"{truck_id} Collect{date_sfx}"
            memo = f"{fmt_date}: Weekly Lease Collection from {driver} {truck_id}"
            je_lines += [
                [fmt_date, "Journal Entry", je_ref, team_name, memo, ACCOUNTS["1800"], amount, ""],
                [fmt_date, "Journal Entry", je_ref, team_name, f"{memo} - Principal", ACCOUNTS["1951"], "", principal],
                [fmt_date, "Journal Entry", je_ref, team_name, f"{memo} - Interest", ACCOUNTS["4300"], "", interest],
            ]
            log_rows.append((pdate, lease.id, amount, principal, interest, program, je_ref, filename))

        elif program == "FLEET_FIRST_MAINTENANCE":
            je_ref = f"{truck_id} Maint{date_sfx}"
            memo = f"{fmt_date}: Maintenance Collection from {driver} {truck_id}"
            je_lines += [
                [fmt_date, "Journal Entry", je_ref, team_name, memo, ACCOUNTS["1800"], amount, ""],
                [fmt_date, "Journal Entry", je_ref, team_name, memo, ACCOUNTS["2603"], "", amount],
            ]
            log_rows.append((pdate, lease.id, amount, 0, 0, program, je_ref, filename))

    # Persist payments
    for (pdate, lease_id, amount, principal, interest, program, je_ref, src) in log_rows:
        p = Payment(
            lease_id=lease_id, payment_date=pdate, amount=amount,
            principal=principal, interest=interest,
            program=program, je_ref=je_ref, source_file=src,
        )
        db.session.add(p)
    db.session.commit()

    # Build QBO CSV
    header = ["Transaction Date", "Transaction Type", "Journal No",
              "Name", "Memo/Description", "Account", "Debit", "Credit"]
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(header)
    w.writerows(je_lines)

    return {
        "qbo_csv": output.getvalue(),
        "je_lines": len(je_lines),
        "lease_payments": sum(1 for r in log_rows if r[5] == "FLEET_FIRST_TRUCK_LEASE"),
        "maint_payments": sum(1 for r in log_rows if r[5] == "FLEET_FIRST_MAINTENANCE"),
        "skipped": len(skipped),
        "warnings": warnings,
    }
