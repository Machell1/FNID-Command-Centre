"""Database type compatibility helpers for PostgreSQL production and SQLite tests."""
import uuid

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import INET as PG_INET
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator

try:
    from geoalchemy2 import Geography as PG_GEOGRAPHY
except ImportError:  # pragma: no cover - optional PostGIS dependency
    PG_GEOGRAPHY = None


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    PostgreSQL uses its native UUID type. SQLite stores UUID values as
    36-character strings so tests can run without a PostgreSQL server.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def UUID(*args, **kwargs):
    return GUID()


def ARRAY(item_type):
    return PG_ARRAY(item_type).with_variant(JSON(), "sqlite")


def GEOGRAPHY(*args, **kwargs):
    if PG_GEOGRAPHY is not None:
        return PG_GEOGRAPHY(*args, **kwargs).with_variant(String(255), "sqlite")
    return String(255)


JSONB = PG_JSONB().with_variant(JSON(), "sqlite")
INET = PG_INET().with_variant(String(45), "sqlite")
