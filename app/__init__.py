from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# Initialize Flask app
app = Flask(__name__)

# Load configurations (you can modify 'config' to load from the environment if necessary)
app.config.from_object('config')

# Initialize database and migrations
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect to 'login' view if user isn't authenticated
login_manager.login_message_category = 'info'  # Flash message category

@login_manager.user_loader
def load_user(user_id):
    # Delayed import to avoid circular import issues
    from .models import User
    return User.query.get(int(user_id))

# Import views and models to register them with the app
from app import views, models
