from flask import Blueprint, render_template
from flask_login import login_required
from .models import Truck, Lease, Payment, Repossession
from sqlalchemy import func
from datetime import date, timedelta

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    # Truck counts by status
    truck_counts = {
        "LEASED": Truck.query.filter_by(status="LEASED").count(),
        "AVAILABLE": Truck.query.filter_by(status="AVAILABLE").count(),
        "REPOSSESSED": Truck.query.filter_by(status="REPOSSESSED").count(),
    }

    # Total lease receivable balance (sum of estimated balances from active leases)
    active_leases = Lease.query.filter_by(status="ACTIVE").all()
    total_receivable = sum(l.estimated_balance for l in active_leases)

    # Total interest income this month
    today = date.today()
    month_start = today.replace(day=1)
    monthly_interest = Payment.query.filter(
        Payment.payment_date >= month_start,
        Payment.program == "FLEET_FIRST_TRUCK_LEASE",
    ).with_entities(func.sum(Payment.interest)).scalar() or 0

    monthly_principal = Payment.query.filter(
        Payment.payment_date >= month_start,
        Payment.program == "FLEET_FIRST_TRUCK_LEASE",
    ).with_entities(func.sum(Payment.principal)).scalar() or 0

    monthly_maint = Payment.query.filter(
        Payment.payment_date >= month_start,
        Payment.program == "FLEET_FIRST_MAINTENANCE",
    ).with_entities(func.sum(Payment.amount)).scalar() or 0

    # Repos this month
    repos_this_month = Repossession.query.filter(
        Repossession.repo_date >= month_start
    ).count()

    # Recent payments (last 10)
    recent_payments = (
        Payment.query
        .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        .limit(10)
        .all()
    )

    # Active leases sorted by balance (largest first) for quick view
    top_leases = sorted(active_leases, key=lambda l: l.estimated_balance, reverse=True)[:10]

    return render_template(
        "dashboard.html",
        truck_counts=truck_counts,
        total_receivable=total_receivable,
        monthly_interest=float(monthly_interest),
        monthly_principal=float(monthly_principal),
        monthly_maint=float(monthly_maint),
        repos_this_month=repos_this_month,
        recent_payments=recent_payments,
        top_leases=top_leases,
        today=today,
    )
