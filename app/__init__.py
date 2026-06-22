import os
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from .models import db, User


def create_app():
    app = Flask(__name__)

    # Config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    db_url = os.environ.get("DATABASE_URL", "sqlite:///fleetfirst.db")
    # Render gives postgres:// but SQLAlchemy needs postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB upload limit

    db.init_app(app)
    Migrate(app, db)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .auth import auth_bp
    from .trucks import trucks_bp
    from .payments import payments_bp
    from .repos import repos_bp
    from .dashboard import dashboard_bp
    from .depreciation import depr_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(trucks_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(repos_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(depr_bp)

    # Jinja2 filters
    @app.template_filter("currency")
    def currency_filter(value):
        if value is None:
            return "—"
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    @app.template_filter("signed_currency")
    def signed_currency_filter(value):
        if value is None:
            return "—"
        v = float(value)
        if v >= 0:
            return f"${v:,.2f}"
        return f"(${abs(v):,.2f})"

    return app
