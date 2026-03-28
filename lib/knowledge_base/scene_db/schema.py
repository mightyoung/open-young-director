"""Database schema initialization for Scene persistence with pgvector."""

import os
from typing import Optional

from psycopg2 import connect
from psycopg2.extras import RealDictCursor


# SQL for creating pgvector extension
ENABLE_PGVECTOR_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
"""

# SQL for creating scenes table
CREATE_SCENES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter INTEGER NOT NULL,
    title TEXT,
    background TEXT,
    location TEXT,
    time_of_day TEXT DEFAULT 'morning',
    emotional_arc JSONB,
    narration TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# SQL for creating plot_beats table
CREATE_PLOT_BEATS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS plot_beats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE,
    beat_type TEXT NOT NULL,
    description TEXT,
    character_interactions JSONB,
    scene_description TEXT,
    narration TEXT,
    sequence INTEGER,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# SQL for creating character_states table
CREATE_CHARACTER_STATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS character_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    beat_id UUID REFERENCES plot_beats(id) ON DELETE CASCADE,
    character_name TEXT NOT NULL,
    emotional_state TEXT,
    dialogue_context TEXT,
    physical_action TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# SQL for creating consumption_records table
CREATE_CONSUMPTION_RECORDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS consumption_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE,
    consumer_type TEXT NOT NULL,
    output_content TEXT,
    status TEXT DEFAULT 'pending',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# SQL for creating indexes
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_beats_embedding ON plot_beats USING ivfflat (embedding vector_cosine_ops)",
    "CREATE INDEX IF NOT EXISTS idx_character_embedding ON character_states USING ivfflat (embedding vector_cosine_ops)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_chapter ON scenes(chapter)",
    "CREATE INDEX IF NOT EXISTS idx_beats_scene ON plot_beats(scene_id)",
    "CREATE INDEX IF NOT EXISTS idx_character_beat ON character_states(beat_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_scene ON consumption_records(scene_id)",
]

# SQL for creating updated_at trigger function
CREATE_UPDATED_AT_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';
"""

# SQL for creating trigger
CREATE_UPDATED_AT_TRIGGER_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_scenes_updated_at') THEN
        CREATE TRIGGER update_scenes_updated_at
            BEFORE UPDATE ON scenes
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END
$$;
"""


def get_database_url() -> str:
    """Get database URL from environment or use default."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@192.168.1.2:45041/intelligence_db"
    )


def parse_database_url(url: str) -> dict:
    """Parse PostgreSQL URL into connection parameters."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/") if parsed.path else None,
    }


def init_schema(database_url: Optional[str] = None) -> bool:
    """Initialize database schema.

    Args:
        database_url: PostgreSQL connection URL. If not provided, reads from DATABASE_URL env.

    Returns:
        True if schema was initialized successfully.

    Raises:
        ConnectionError: If cannot connect to database.
        RuntimeError: If schema initialization fails.
    """
    url = database_url or get_database_url()
    params = parse_database_url(url)

    if not params["database"]:
        raise ValueError("Database name is required in the connection URL")

    try:
        conn = connect(**params)
        cursor = conn.cursor()

        # Enable pgvector extension
        cursor.execute(ENABLE_PGVECTOR_SQL)

        # Create tables
        cursor.execute(CREATE_SCENES_TABLE_SQL)
        cursor.execute(CREATE_PLOT_BEATS_TABLE_SQL)
        cursor.execute(CREATE_CHARACTER_STATES_TABLE_SQL)
        cursor.execute(CREATE_CONSUMPTION_RECORDS_TABLE_SQL)

        # Create indexes
        for index_sql in CREATE_INDEXES_SQL:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                # Index might already exist or ivfflat not available
                # Fall back to gin index for vector columns
                if "ivfflat" in str(e).lower() or "embedding" in str(e).lower():
                    fallback_sql = index_sql.replace("USING ivfflat", "USING gin")
                    try:
                        cursor.execute(fallback_sql)
                    except Exception:
                        pass  # Index creation is best effort

        # Create updated_at trigger
        cursor.execute(CREATE_UPDATED_AT_FUNCTION_SQL)
        cursor.execute(CREATE_UPDATED_AT_TRIGGER_SQL)

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        raise RuntimeError(f"Failed to initialize database schema: {e}") from e


def check_connection(database_url: Optional[str] = None) -> bool:
    """Check if database connection is working.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        True if connection is successful.
    """
    url = database_url or get_database_url()
    params = parse_database_url(url)

    try:
        conn = connect(**params)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


def get_connection(database_url: Optional[str] = None):
    """Get a database connection.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        psycopg2 connection object.
    """
    url = database_url or get_database_url()
    params = parse_database_url(url)

    if not params["database"]:
        raise ValueError("Database name is required in the connection URL")

    return connect(**params)
