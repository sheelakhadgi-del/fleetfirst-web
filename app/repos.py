import csv, io
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, Response)
from flask_login import login_required
from .models import db, Truck, Lease, Repossession, RepoExpense
from core.repo_calc import calc_repo, months_of_depreciation, book_value as calc_book_value
from core.schedule import build_schedule, get_week_for_date

repos_bp = Blueprint("repos", __name__, url_prefix="/repos")


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(s, default=0.0):
    try:
        return float(str(s).replace("$", "").replace(",", "").strip() or default)
    except (ValueError, TypeError):
        return default


@repos_bp.route("/")
@login_required
def list_repos():
    repos = (Repossession.query
             .join(Truck)
             .order_by(Repossession.repo_date.desc())
             .all())
    return render_template("repos/list.html", repos=repos)


@repos_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_repo():
    # Pre-fill VIN from query param
    vin = request.args.get("vin", "").strip()
    truck = Truck.query.filter_by(vin=vin).first() if vin else None
    lease = truck.active_lease if truck else None

    if request.method == "POST":
        vin = request.form.get("vin", "").strip().upper()
        truck = Truck.query.filter_by(vin=vin).first()
        if not truck:
            flash(f"Truck {vin} not found.", "danger")
            return render_template("repos/new.html", truck=None, lease=None)

        lease = truck.active_lease
        if not lease:
            flash("No active lease found for this truck.", "danger")
            return render_template("repos/new.html", truck=truck, lease=None)

        repo_date = _parse_date(request.form.get("repo_date"))
        if not repo_date:
            flash("Repo date is required.", "danger")
            return render_template("repos/new.html", truck=truck, lease=lease)

        principal_bal = _parse_float(request.form.get("principal_balance"))
        interest_bal = _parse_float(request.form.get("interest_balance"))
        deposit = _parse_float(request.form.get("deposit_forfeited"))
        maint_dep = _parse_float(request.form.get("maintenance_deposit"))
        fmv = _parse_float(request.form.get("fmv"))
        notes = request.form.get("notes", "").strip()

        # Calculate book value
        acq_date = truck.acquisition_date
        acq_cost = float(truck.acquisition_cost or 0)
        useful_life = truck.useful_life_months or 65

        result = calc_repo(
            original_cost=acq_cost,
            useful_life_months=useful_life,
            acq_date=acq_date,
            repo_date=repo_date,
            principal_balance=principal_bal,
            interest_balance=interest_bal,
            deposit_forfeited=deposit,
            maintenance_deposit=maint_dep,
            asset_account=truck.asset_account,
        )

        repo = Repossession(
            truck_id=truck.id,
            lease_id=lease.id,
            repo_date=repo_date,
            principal_balance=principal_bal,
            interest_balance=interest_bal,
            deposit_forfeited=deposit,
            maintenance_deposit=maint_dep,
            book_value=result["book_value"],
            accumulated_depreciation=result["accumulated_depreciation"],
            gain_loss=result["gain_loss"],
            fmv=fmv if fmv else None,
            notes=notes,
        )
        db.session.add(repo)

        # Update statuses
        lease.status = "REPOSSESSED"
        lease.ended_at = datetime.utcnow()
        truck.status = "AVAILABLE"   # Available to re-lease after repo

        db.session.commit()
        flash(f"Repossession recorded for {truck.vin}. Gain/Loss: ${result['gain_loss']:,.2f}", "success")
        return redirect(url_for("repos.detail", repo_id=repo.id))

    # GET — pre-calculate if truck+lease available
    prefill = {}
    if truck and lease:
        acq_cost = float(truck.acquisition_cost or 0)
        useful_life = truck.useful_life_months or 65
        acq_date = truck.acquisition_date
        today = date.today()

        # Get principal balance from schedule
        sched = build_schedule(
            lease.lease_start, lease.term_weeks,
            float(lease.initial_balance), float(lease.weekly_payment),
            float(lease.annual_rate)
        )
        prefill["principal_balance"] = f"{lease.estimated_balance:.2f}"
        prefill["interest_balance"] = "0.00"
        if acq_date and acq_cost:
            bv = calc_book_value(acq_cost, useful_life, acq_date, today)
            prefill["book_value_preview"] = f"{bv:,.2f}"
            prefill["months_depreciated"] = months_of_depreciation(acq_date, today)

    return render_template("repos/new.html", truck=truck, lease=lease, prefill=prefill)


@repos_bp.route("/<int:repo_id>")
@login_required
def detail(repo_id):
    repo = Repossession.query.get_or_404(repo_id)
    truck = repo.truck
    lease = repo.lease

    result = calc_repo(
        original_cost=float(truck.acquisition_cost or 0),
        useful_life_months=truck.useful_life_months or 65,
        acq_date=truck.acquisition_date,
        repo_date=repo.repo_date,
        principal_balance=float(repo.principal_balance),
        interest_balance=float(repo.interest_balance or 0),
        deposit_forfeited=float(repo.deposit_forfeited or 0),
        maintenance_deposit=float(repo.maintenance_deposit or 0),
        asset_account=truck.asset_account,
    )

    return render_template("repos/detail.html", repo=repo, truck=truck,
                           lease=lease, je_lines=result["je_lines"], result=result)


@repos_bp.route("/<int:repo_id>/export-je")
@login_required
def export_je(repo_id):
    repo = Repossession.query.get_or_404(repo_id)
    truck = repo.truck

    result = calc_repo(
        original_cost=float(truck.acquisition_cost or 0),
        useful_life_months=truck.useful_life_months or 65,
        acq_date=truck.acquisition_date,
        repo_date=repo.repo_date,
        principal_balance=float(repo.principal_balance),
        interest_balance=float(repo.interest_balance or 0),
        deposit_forfeited=float(repo.deposit_forfeited or 0),
        maintenance_deposit=float(repo.maintenance_deposit or 0),
        asset_account=truck.asset_account,
    )

    fmt_date = repo.repo_date.strftime("%m/%d/%Y")
    je_ref = f"{truck.truck_id} Repo{repo.repo_date.strftime('%m%d%y')}"
    driver = repo.lease.driver_name or ""

    header = ["Transaction Date", "Transaction Type", "Journal No",
              "Name", "Memo/Description", "Account", "Debit", "Credit"]
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(header)
    for line in result["je_lines"]:
        w.writerow([
            fmt_date, "Journal Entry", je_ref, driver,
            line["description"],
            line["account"],
            line["debit"] if line["debit"] != "" else "",
            line["credit"] if line["credit"] != "" else "",
        ])

    repo.je_exported = True
    db.session.commit()

    filename = f"{truck.truck_id}_Repo_{repo.repo_date.strftime('%m%d%y')}_QBO_JE.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@repos_bp.route("/<int:repo_id>/expenses/add", methods=["POST"])
@login_required
def add_expense(repo_id):
    repo = Repossession.query.get_or_404(repo_id)
    exp = RepoExpense(
        repo_id=repo_id,
        expense_date=_parse_date(request.form.get("expense_date")),
        vendor=request.form.get("vendor", "").strip(),
        description=request.form.get("description", "").strip(),
        amount=_parse_float(request.form.get("amount")),
        bill_ref=request.form.get("bill_ref", "").strip(),
    )
    db.session.add(exp)
    db.session.commit()
    flash("Expense added.", "success")
    return redirect(url_for("repos.detail", repo_id=repo_id))


@repos_bp.route("/api/book-value")
@login_required
def api_book_value():
    """AJAX endpoint to calculate book value for a given VIN and repo date."""
    from flask import jsonify
    vin = request.args.get("vin", "").strip().upper()
    repo_date_str = request.args.get("repo_date", "").strip()
    truck = Truck.query.filter_by(vin=vin).first()
    if not truck or not truck.acquisition_date or not truck.acquisition_cost:
        return jsonify({"error": "Truck not found or missing acquisition data"})

    repo_date = _parse_date(repo_date_str)
    if not repo_date:
        return jsonify({"error": "Invalid repo date"})

    bv = calc_book_value(
        float(truck.acquisition_cost),
        truck.useful_life_months or 65,
        truck.acquisition_date,
        repo_date,
    )
    months = months_of_depreciation(truck.acquisition_date, repo_date)
    lease = truck.active_lease
    principal = float(lease.estimated_balance) if lease else 0.0

    return jsonify({
        "book_value": round(bv, 2),
        "months_depreciated": months,
        "principal_balance": round(principal, 2),
        "acquisition_cost": float(truck.acquisition_cost),
        "useful_life_months": truck.useful_life_months,
    })
