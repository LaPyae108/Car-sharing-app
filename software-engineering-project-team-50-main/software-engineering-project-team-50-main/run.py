from app import app, socketio
from app.extensions import db
from app.models import User, UserRole, DiscountRule
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create tables if they don't exist
    db.create_all()

    # --- Seed superadmin user ---
    superadmin_email = "admin@mm.com"
    if not User.query.filter_by(email=superadmin_email).first():
        superadmin = User(
            firstname="Super",
            lastname="Admin",
            email=superadmin_email,
            password=generate_password_hash("12345"),  # change in prod
            role=UserRole.superadmin
        )
        db.session.add(superadmin)

    # --- Seed discount rule ---
    rule_name = "Weekly Commuter"
    if not DiscountRule.query.filter_by(rule_name=rule_name).first():
        discount = DiscountRule(
            rule_name=rule_name,
            min_trips=4,
            discount_percentage=10.0,
            is_active=True
        )
        db.session.add(discount)

    # Commit both seeding operations together
    db.session.commit()

if __name__ == "__main__":
    socketio.run(app, debug=True, host='127.0.0.1', port=5001)
