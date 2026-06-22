from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("dashboard.index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/users")
@login_required
def users():
    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard.index"))
    all_users = User.query.order_by(User.name).all()
    return render_template("auth/users.html", users=all_users)


@auth_bp.route("/users/add", methods=["GET", "POST"])
@login_required
def add_user():
    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "accountant")
        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
        else:
            u = User(email=email, name=name, role=role)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash(f"User {name} created.", "success")
            return redirect(url_for("auth.users"))
    return render_template("auth/add_user.html")


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password updated.", "success")
    return render_template("auth/profile.html")
