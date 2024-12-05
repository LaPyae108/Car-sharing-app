import os
# Enable CSRF protection for Flask-WTF
WTF_CSRF_ENABLED = True

# Secret key for securely signing the session cookie and other security-related uses
SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-secret')

# Base directory for the app
basedir = os.path.abspath(os.path.dirname(__file__))

# Database configuration
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'app.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False
