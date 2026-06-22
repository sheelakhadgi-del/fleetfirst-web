from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from datetime import date, datetime
from .models import db, Truck, Lease
from core.schedule import build_schedule

trucks_bp = Blueprint("trucks", __name__, url_prefix="/trucks")


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


@trucks_bp.route("/")
@login_required
def list_trucks():
    status_filter = request.args.get("status", "")
    q = Truck.query.order_by(Truck.truck_id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    trucks = q.all()
    return render_template("trucks/list.html", trucks=trucks, status_filter=status_filter)


@trucks_bp.route("/<vin>")
@login_required
def detail(vin):
    truck = Truck.query.filter_by(vin=vin).first_or_404()
    lease = truck.active_lease
    schedule = None
    current_week = None
    if lease:
        schedule = build_schedule(
            lease.lease_start, lease.term_weeks,
            float(lease.initial_balance), float(lease.weekly_payment),
            float(lease.annual_rate)
        )
        today = date.today()
        for entry in schedule:
            if entry["start_date"].date() <= today <= entry["end_date"].date():
                current_week = entry
                break
        if not current_week and schedule:
            # Past the last week
            for entry in reversed(schedule):
                if entry["start_date"].date() <= today:
                    current_week = entry
                    break

    return render_template(
        "trucks/detail.html",
        truck=truck,
        lease=lease,
        schedule=schedule,
        current_week=current_week,
    )


@trucks_bp.route("/<vin>/schedule")
@login_required
def schedule_view(vin):
    truck = Truck.query.filter_by(vin=vin).first_or_404()
    lease = truck.active_lease
    if not lease:
        # Show last lease's schedule
        lease = Lease.query.filter_by(truck_id=truck.id).order_by(Lease.created_at.desc()).first()
    if not lease:
        flash("No lease found for this truck.", "warning")
        return redirect(url_for("trucks.detail", vin=vin))

    schedule = build_schedule(
        lease.lease_start, lease.term_weeks,
        float(lease.initial_balance), float(lease.weekly_payment),
        float(lease.annual_rate)
    )
    today = date.today()
    current_week_num = None
    for entry in schedule:
        if entry["start_date"].date() <= today <= entry["end_date"].date():
            current_week_num = entry["week"]
            break

    return render_template(
        "trucks/schedule.html",
        truck=truck,
        lease=lease,
        schedule=schedule,
        current_week_num=current_week_num,
    )


@trucks_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        vin = request.form.get("vin", "").strip().upper()
        if not vin:
            flash("VIN is required.", "danger")
            return render_template("trucks/add.html")
        if Truck.query.filter_by(vin=vin).first():
            flash(f"Truck {vin} already exists.", "danger")
            return render_template("trucks/add.html")

        truck = Truck(
            vin=vin,
            truck_id=request.form.get("truck_id", "").strip(),
            description=request.form.get("description", "").strip(),
            acquisition_date=_parse_date(request.form.get("acquisition_date")),
            acquisition_cost=request.form.get("acquisition_cost") or None,
            residual_value=float(request.form.get("residual_value") or 5000),
            useful_life_months=int(request.form.get("useful_life_months") or 60),
            asset_account=request.form.get("asset_account", "1504"),
            status=request.form.get("status", "AVAILABLE"),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(truck)
        db.session.flush()

        # Optionally add a lease at the same time
        if request.form.get("add_lease") == "yes":
            _add_lease_from_form(truck, request.form)

        db.session.commit()
        flash(f"Truck {vin} added.", "success")
        return redirect(url_for("trucks.detail", vin=vin))

    return render_template("trucks/add.html")


@trucks_bp.route("/<vin>/edit", methods=["GET", "POST"])
@login_required
def edit(vin):
    truck = Truck.query.filter_by(vin=vin).first_or_404()
    if request.method == "POST":
        truck.truck_id = request.form.get("truck_id", "").strip()
        truck.description = request.form.get("description", "").strip()
        truck.acquisition_date = _parse_date(request.form.get("acquisition_date"))
        truck.acquisition_cost = request.form.get("acquisition_cost") or None
        truck.residual_value = float(request.form.get("residual_value") or 5000)
        truck.useful_life_months = int(request.form.get("useful_life_months") or 60)
        truck.asset_account = request.form.get("asset_account", "1504")
        truck.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Truck updated.", "success")
        return redirect(url_for("trucks.detail", vin=vin))
    return render_template("trucks/edit.html", truck=truck)


@trucks_bp.route("/<vin>/lease/add", methods=["GET", "POST"])
@login_required
def add_lease(vin):
    truck = Truck.query.filter_by(vin=vin).first_or_404()
    if request.method == "POST":
        lease = _add_lease_from_form(truck, request.form)
        if lease:
            truck.status = "LEASED"
            db.session.commit()
            flash(f"Lease added for {truck.vin}.", "success")
            return redirect(url_for("trucks.detail", vin=vin))
    return render_template("trucks/add_lease.html", truck=truck)


def _add_lease_from_form(truck, form):
    try:
        lease = Lease(
            truck_id=truck.id,
            driver_name=form.get("driver_name", "").strip(),
            team_name=form.get("team_name", "").strip(),
            team_id=form.get("team_id", "").strip(),
            lease_start=_parse_date(form.get("lease_start")),
            term_months=int(form.get("term_months") or 32),
            initial_balance=float(form.get("initial_balance") or 0),
            weekly_payment=float(form.get("weekly_payment") or 0),
            annual_rate=float(form.get("annual_rate") or 0.1034),
            notes=form.get("lease_notes", "").strip(),
        )
        db.session.add(lease)
        return lease
    except Exception as e:
        flash(f"Error adding lease: {e}", "danger")
        return None
