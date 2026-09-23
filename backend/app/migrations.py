"""Add ownership without exposing or overwriting pre-account records."""
from sqlalchemy import inspect, text

from .models import Base


def migrate_schema(connection):
    Base.metadata.create_all(connection)
    for table in ("assessments", "feedback"):
        columns = {column["name"] for column in inspect(connection).get_columns(table)}
        if "user_id" not in columns:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR(36) REFERENCES users(id)"))
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"))
    # Legacy rows deliberately keep user_id=NULL; they belong to no new account.
