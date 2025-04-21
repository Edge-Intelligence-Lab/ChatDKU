from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
# A different file to avoid circular imports. Future updates can include structuring the backend using methods or flask blueprints