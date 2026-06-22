from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), default="accountant")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Truck(db.Model):
    __tablename__ = "trucks"
    id = db.Column(db.Integer, primary_key=True)
    vin = db.Column(db.String(17), unique=True, nullable=False)
    truck_id = db.Column(db.String(20))          # e.g. J462765
    description = db.Column(db.String(100))      # e.g. 2022 Kenworth T680
    acquisition_date = db.Column(db.Date)
    acquisition_cost = db.Column(db.Numeric(12, 2))   # cost recorded in 1504/1950
    residual_value = db.Column(db.Numeric(12, 2), default=5000)
    useful_life_months = db.Column(db.Integer, default=60)  # always 60 per policy
    asset_account = db.Column(db.String(10), default="1504")  # 1504 or 1950
    status = db.Column(db.String(20), default="AVAILABLE")    # AVAILABLE / LEASED / REPOSSESSED
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    leases = db.relationship("Lease", back_populates="truck", lazy=True,
                             order_by="Lease.lease_start")
    repos = db.relationship("Repossession", back_populates="truck", lazy=True)
    depreciation_periods = db.relationship("DepreciationPeriod", back_populates="truck",
                                           lazy=True, order_by="DepreciationPeriod.start_date")

    @property
    def active_lease(self):
        return next((l for l in self.leases if l.status == "ACTIVE"), None)

    @property
    def display_name(self):
        return f"{self.truck_id or ''} — {self.description or self.vin}"

    def __repr__(self):
        return f"<Truck {self.vin}>"


class Lease(db.Model):
    __tablename__ = "leases"
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey("trucks.id"), nullable=False)
    driver_name = db.Column(db.String(100))
    team_name = db.Column(db.String(100))
    team_id = db.Column(db.String(60))
    lease_start = db.Column(db.Date, nullable=False)
    term_months = db.Column(db.Integer, default=32)
    initial_balance = db.Column(db.Numeric(12, 2), nullable=False)
    weekly_payment = db.Column(db.Numeric(10, 2), nullable=False)
    annual_rate = db.Column(db.Numeric(6, 4), default=0.1034)
    status = db.Column(db.String(20), default="ACTIVE")   # ACTIVE / TERMINATED / REPOSSESSED
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)

    truck = db.relationship("Truck", back_populates="leases")
    payments = db.relationship("Payment", back_populates="lease", lazy=True,
                               order_by="Payment.payment_date")
    repossession = db.relationship("Repossession", back_populates="lease", uselist=False)

    @property
    def term_weeks(self):
        return self.term_months * 4

    @property
    def total_collected(self):
        return sum(float(p.amount) for p in self.payments if p.program == "FLEET_FIRST_TRUCK_LEASE")

    @property
    def total_principal_paid(self):
        return sum(float(p.principal or 0) for p in self.payments if p.program == "FLEET_FIRST_TRUCK_LEASE")

    @property
    def estimated_balance(self):
        return round(float(self.initial_balance) - self.total_principal_paid, 2)

    def __repr__(self):
        return f"<Lease {self.id} {self.driver_name}>"


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    lease_id = db.Column(db.Integer, db.ForeignKey("leases.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    principal = db.Column(db.Numeric(10, 2))
    interest = db.Column(db.Numeric(10, 2))
    program = db.Column(db.String(40))     # FLEET_FIRST_TRUCK_LEASE or FLEET_FIRST_MAINTENANCE
    je_ref = db.Column(db.String(60))
    source_file = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lease = db.relationship("Lease", back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.id} {self.payment_date} ${self.amount}>"


class Repossession(db.Model):
    __tablename__ = "repossessions"
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey("trucks.id"), nullable=False)
    lease_id = db.Column(db.Integer, db.ForeignKey("leases.id"), nullable=False)
    repo_date = db.Column(db.Date, nullable=False)
    principal_balance = db.Column(db.Numeric(12, 2), nullable=False)
    interest_balance = db.Column(db.Numeric(12, 2), default=0)
    deposit_forfeited = db.Column(db.Numeric(10, 2), default=0)
    maintenance_deposit = db.Column(db.Numeric(10, 2), default=0)
    book_value = db.Column(db.Numeric(12, 2))
    accumulated_depreciation = db.Column(db.Numeric(12, 2))
    gain_loss = db.Column(db.Numeric(12, 2))
    fmv = db.Column(db.Numeric(12, 2))
    notes = db.Column(db.Text)
    je_exported = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    truck = db.relationship("Truck", back_populates="repos")
    lease = db.relationship("Lease", back_populates="repossession")
    expenses = db.relationship("RepoExpense", back_populates="repossession", lazy=True)

    @property
    def total_expenses(self):
        return sum(float(e.amount) for e in self.expenses)

    def __repr__(self):
        return f"<Repossession {self.id} {self.repo_date}>"


class DepreciationPeriod(db.Model):
    """One straight-line depreciation period for a truck.
    A truck may have multiple periods if it was repo'd and re-leased (re-seated)."""
    __tablename__ = "depreciation_periods"
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey("trucks.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)   # first month of depreciation
    end_date = db.Column(db.Date)                      # last month (None = still depreciating)
    cost_basis = db.Column(db.Numeric(12, 2), nullable=False)
    residual_value = db.Column(db.Numeric(12, 2), default=5000)
    life_months = db.Column(db.Integer, default=60)
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    truck = db.relationship("Truck", back_populates="depreciation_periods")

    @property
    def monthly_depreciation(self):
        return round((float(self.cost_basis) - float(self.residual_value)) / self.life_months, 2)

    def __repr__(self):
        return f"<DepreciationPeriod truck={self.truck_id} start={self.start_date}>"


class RepoExpense(db.Model):
    __tablename__ = "repo_expenses"
    id = db.Column(db.Integer, primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey("repossessions.id"), nullable=False)
    expense_date = db.Column(db.Date)
    vendor = db.Column(db.String(100))
    description = db.Column(db.String(200))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bill_ref = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    repossession = db.relationship("Repossession", back_populates="expenses")
