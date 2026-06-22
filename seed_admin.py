"""
Run once after first deploy to create the admin user and migrate existing lease data.
    python seed_admin.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import db, User, Truck, Lease

app = create_app()

def create_admin():
    email = input("Admin email: ").strip().lower()
    name  = input("Admin name: ").strip()
    pw    = input("Password: ").strip()

    with app.app_context():
        if User.query.filter_by(email=email).first():
            print(f"User {email} already exists.")
            return
        u = User(email=email, name=name, role="admin")
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        print(f"Admin user {email} created.")


def migrate_from_sqlite():
    """
    Pull lease data from the existing fleetfirst_automation/fleetfirst.db
    and insert into the web app's database.
    """
    import sqlite3
    from datetime import datetime

    sqlite_path = os.path.join(
        os.path.dirname(__file__), "..", "fleetfirst_automation", "fleetfirst.db"
    )
    if not os.path.exists(sqlite_path):
        print(f"No SQLite DB found at {sqlite_path}")
        return

    conn = sqlite3.connect(sqlite_path)
    rows = conn.execute("""
        SELECT vin, team_id, team_name, driver_name, truck_id,
               lease_start, term_weeks, initial_balance, weekly_payment,
               annual_rate, asset_account
        FROM leases
    """).fetchall()
    conn.close()

    count = 0
    with app.app_context():
        for row in rows:
            (vin, team_id, team_name, driver_name, truck_id,
             lease_start, term_weeks, initial_balance, weekly_payment,
             annual_rate, asset_account) = row

            if Truck.query.filter_by(vin=vin).first():
                continue  # already imported

            truck = Truck(
                vin=vin,
                truck_id=truck_id,
                asset_account=asset_account or "1504",
                status="LEASED",
            )
            db.session.add(truck)
            db.session.flush()

            try:
                ls = datetime.strptime(lease_start, "%m/%d/%Y").date()
            except Exception:
                try:
                    ls = datetime.strptime(lease_start, "%Y-%m-%d").date()
                except Exception:
                    ls = None

            if ls:
                lease = Lease(
                    truck_id=truck.id,
                    driver_name=driver_name,
                    team_name=team_name,
                    team_id=team_id,
                    lease_start=ls,
                    term_months=(term_weeks or 128) // 4,
                    initial_balance=initial_balance or 0,
                    weekly_payment=weekly_payment or 0,
                    annual_rate=annual_rate or 0.1034,
                    status="ACTIVE",
                )
                db.session.add(lease)
            count += 1

        db.session.commit()
        print(f"Migrated {count} trucks/leases from fleetfirst.db")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("1. Create admin user")
    print("2. Migrate leases from existing fleetfirst.db")
    choice = input("Choose (1/2/both): ").strip()
    if choice in ("1", "both"):
        create_admin()
    if choice in ("2", "both"):
        migrate_from_sqlite()
