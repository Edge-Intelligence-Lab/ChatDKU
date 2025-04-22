from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin

db = SQLAlchemy()
migrate = Migrate()
admin=Admin(name="Dashboard", template_mode="bootstrap4")
# A different file to avoid circular imports. Future updates can include structuring the backend using methods or flask blueprints