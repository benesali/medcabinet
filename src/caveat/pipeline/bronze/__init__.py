"""Bronze pipeline package. Shared SQLAlchemy metadata lives here."""

from sqlalchemy import MetaData

metadata = MetaData(schema="bronze")
