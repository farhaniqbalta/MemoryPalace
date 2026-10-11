"""Verify migrations and chunk storage in a dedicated local verification database.

Does not call AI providers or alter application rows. Keeps the verification DB
for inspection; repeated runs verify the already-migrated schema.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk

url = create_engine(settings.database_url).url
database = "memorypalace_migration_check"
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as connection:
    exists = connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
    ).scalar()
    if not exists:
        connection.execute(text('CREATE DATABASE "memorypalace_migration_check"'))
admin.dispose()

check_url = url.set(database=database)
engine = create_engine(check_url)
env = dict(os.environ, DATABASE_URL=check_url.render_as_string(hide_password=False))


def migrate(revision):
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision], env=env, check=True)


if not inspect(engine).has_table("alembic_version"):
    migrate("0001")
    assert inspect(engine).has_table("knowledge_cards")
    assert not inspect(engine).has_table("chunks")
    print("Fresh database migrated to the existing schema.")
migrate("head")
assert inspect(engine).has_table("knowledge_cards")
assert inspect(engine).has_table("raw_sources")
assert inspect(engine).has_table("chunks")
with engine.connect() as connection:
    assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
    vector_type = connection.execute(text(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
    )).scalar()
    assert vector_type == "vector(1536)"

with Session(engine) as session:
    source = "verification/" + str(uuid.uuid4())
    chunk = Chunk(source=source, chunk_index=0, content="Migration check",
                  source_metadata={"format": "markdown"}, embedding=[1.0] + [0.0] * 1535,
                  embedding_model="gemini:gemini-embedding-001")
    session.add(chunk)
    session.flush()
    session.expire_all()
    loaded = session.get(Chunk, chunk.id)
    assert loaded.source_metadata == {"format": "markdown"}
    assert len(loaded.embedding) == 1536
    assert loaded.created_at is not None
    session.rollback()
print("Migration, legacy-table preservation, vector size, and ORM round-trip verified.")
engine.dispose()
