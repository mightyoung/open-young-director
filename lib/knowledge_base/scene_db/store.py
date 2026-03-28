"""Scene Store - PostgreSQL + pgvector persistence layer for narrative scenes."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import numpy as np

from .models import (
    BeatType,
    CharacterState,
    ConsumptionRecord,
    ConsumptionType,
    PlotBeat,
    Scene,
    SceneStatus,
)
from .schema import get_connection, get_database_url, init_schema


class SceneStore:
    """Scene persistence store with vector search support.

    Provides CRUD operations for scenes, plot beats, character states,
    and consumption records with PostgreSQL + pgvector backend.

    Example:
        store = SceneStore()
        store.init_db()

        scene = store.create_scene({
            "chapter": 1,
            "title": "开场",
            "background": "未来城市",
        })

        beat = store.add_beat(scene["id"], {
            "beat_type": "OPENING",
            "description": "主角登场",
            "embedding": [0.1, 0.2, ...],
        })
    """

    def __init__(self, database_url: Optional[str] = None):
        """Initialize SceneStore.

        Args:
            database_url: PostgreSQL connection URL. Defaults to DATABASE_URL env.
        """
        self.database_url = database_url or get_database_url()
        self._connection_params = self._parse_url(self.database_url)

    def _parse_url(self, url: str) -> dict:
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

    def _get_connection(self):
        """Get a new database connection."""
        return get_connection(self.database_url)

    def init_db(self) -> bool:
        """Initialize database schema.

        Returns:
            True if initialization was successful.
        """
        return init_schema(self.database_url)

    # -------------------------------------------------------------------------
    # Scene Operations
    # -------------------------------------------------------------------------

    def create_scene(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new scene.

        Args:
            scene_data: Scene data dict with keys:
                - chapter (required): Chapter number
                - title (optional): Scene title
                - background (optional): Chapter background/outline
                - location (optional): Scene location
                - time_of_day (optional): Time of day, default 'morning'
                - emotional_arc (optional): Dict with start, peak, end emotional arc
                - narration (optional): Narration text
                - status (optional): Scene status, default 'pending'

        Returns:
            Created scene as dict including generated id.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        emotional_arc = scene_data.get("emotional_arc")
        if emotional_arc and not isinstance(emotional_arc, str):
            emotional_arc = json.dumps(emotional_arc)

        cursor.execute(
            """
            INSERT INTO scenes (chapter, title, background, location, time_of_day,
                              emotional_arc, narration, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, chapter, title, background, location, time_of_day,
                     emotional_arc, narration, status, created_at, updated_at
            """,
            (
                scene_data["chapter"],
                scene_data.get("title"),
                scene_data.get("background"),
                scene_data.get("location"),
                scene_data.get("time_of_day", "morning"),
                emotional_arc,
                scene_data.get("narration"),
                scene_data.get("status", "pending"),
            ),
        )

        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return self._row_to_scene_dict(row)

    def get_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Get a scene by ID.

        Args:
            scene_id: Scene UUID string.

        Returns:
            Scene dict or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, chapter, title, background, location, time_of_day,
                   emotional_arc, narration, status, created_at, updated_at
            FROM scenes WHERE id = %s
            """,
            (scene_id,),
        )

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return self._row_to_scene_dict(row)
        return None

    def update_scene(self, scene_id: str, scene_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a scene.

        Args:
            scene_id: Scene UUID string.
            scene_data: Fields to update.

        Returns:
            Updated scene dict or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build dynamic update query
        allowed_fields = ["title", "background", "location", "time_of_day",
                         "emotional_arc", "narration", "status"]
        updates = []
        values = []

        for field in allowed_fields:
            if field in scene_data:
                value = scene_data[field]
                if field == "emotional_arc" and value and not isinstance(value, str):
                    value = json.dumps(value)
                updates.append(f"{field} = %s")
                values.append(value)

        if not updates:
            return self.get_scene(scene_id)

        values.append(scene_id)
        query = f"UPDATE scenes SET {', '.join(updates)} WHERE id = %s RETURNING *"

        cursor.execute(query, tuple(values))
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if row:
            return self._row_to_scene_dict(row)
        return None

    def delete_scene(self, scene_id: str) -> bool:
        """Delete a scene and all related data (cascades).

        Args:
            scene_id: Scene UUID string.

        Returns:
            True if deleted, False if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM scenes WHERE id = %s", (scene_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()

        return deleted

    def list_scenes(self, chapter: Optional[int] = None, limit: int = 100,
                   offset: int = 0) -> List[Dict[str, Any]]:
        """List scenes with optional chapter filter.

        Args:
            chapter: Filter by chapter number.
            limit: Maximum number of scenes to return.
            offset: Number of scenes to skip.

        Returns:
            List of scene dicts.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if chapter is not None:
            cursor.execute(
                """
                SELECT id, chapter, title, background, location, time_of_day,
                       emotional_arc, narration, status, created_at, updated_at
                FROM scenes WHERE chapter = %s
                ORDER BY created_at DESC LIMIT %s OFFSET %s
                """,
                (chapter, limit, offset),
            )
        else:
            cursor.execute(
                """
                SELECT id, chapter, title, background, location, time_of_day,
                       emotional_arc, narration, status, created_at, updated_at
                FROM scenes
                ORDER BY created_at DESC LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_scene_dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Plot Beat Operations
    # -------------------------------------------------------------------------

    def add_beat(self, scene_id: str, beat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a plot beat to a scene.

        Args:
            scene_id: Scene UUID string.
            beat_data: Beat data with keys:
                - beat_type (required): OPENING/DEVELOPMENT/CONFLICT/CLIMAX/RESOLUTION/TRANSITION
                - description (optional): Beat description
                - character_interactions (optional): List of character interaction dicts
                - scene_description (optional): Scene description
                - narration (optional): Narration text
                - sequence (optional): Beat sequence number
                - embedding (optional): Vector embedding for semantic search

        Returns:
            Created plot beat as dict.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        character_interactions = beat_data.get("character_interactions")
        if character_interactions and not isinstance(character_interactions, str):
            character_interactions = json.dumps(character_interactions)

        embedding = beat_data.get("embedding")
        if embedding is not None:
            embedding = np.array(embedding).tolist()

        cursor.execute(
            """
            INSERT INTO plot_beats (scene_id, beat_type, description, character_interactions,
                                  scene_description, narration, sequence, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, scene_id, beat_type, description, character_interactions,
                     scene_description, narration, sequence, embedding, created_at
            """,
            (
                scene_id,
                beat_data["beat_type"],
                beat_data.get("description"),
                character_interactions,
                beat_data.get("scene_description"),
                beat_data.get("narration"),
                beat_data.get("sequence"),
                embedding,
            ),
        )

        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return self._row_to_beat_dict(row)

    def get_beat(self, beat_id: str) -> Optional[Dict[str, Any]]:
        """Get a plot beat by ID.

        Args:
            beat_id: Beat UUID string.

        Returns:
            Beat dict or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, scene_id, beat_type, description, character_interactions,
                   scene_description, narration, sequence, embedding, created_at
            FROM plot_beats WHERE id = %s
            """,
            (beat_id,),
        )

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return self._row_to_beat_dict(row)
        return None

    def get_beats_for_scene(self, scene_id: str) -> List[Dict[str, Any]]:
        """Get all plot beats for a scene.

        Args:
            scene_id: Scene UUID string.

        Returns:
            List of beat dicts ordered by sequence.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, scene_id, beat_type, description, character_interactions,
                   scene_description, narration, sequence, embedding, created_at
            FROM plot_beats
            WHERE scene_id = %s
            ORDER BY sequence ASC, created_at ASC
            """,
            (scene_id,),
        )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_beat_dict(row) for row in rows]

    def update_beat(self, beat_id: str, beat_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a plot beat.

        Args:
            beat_id: Beat UUID string.
            beat_data: Fields to update.

        Returns:
            Updated beat dict or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        allowed_fields = ["beat_type", "description", "character_interactions",
                         "scene_description", "narration", "sequence", "embedding"]
        updates = []
        values = []

        for field in allowed_fields:
            if field in beat_data:
                value = beat_data[field]
                if field == "character_interactions" and value and not isinstance(value, str):
                    value = json.dumps(value)
                if field == "embedding" and value is not None:
                    value = np.array(value).tolist()
                updates.append(f"{field} = %s")
                values.append(value)

        if not updates:
            return self.get_beat(beat_id)

        values.append(beat_id)
        query = f"UPDATE plot_beats SET {', '.join(updates)} WHERE id = %s RETURNING *"

        cursor.execute(query, tuple(values))
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if row:
            return self._row_to_beat_dict(row)
        return None

    def delete_beat(self, beat_id: str) -> bool:
        """Delete a plot beat.

        Args:
            beat_id: Beat UUID string.

        Returns:
            True if deleted, False if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM plot_beats WHERE id = %s", (beat_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()

        return deleted

    # -------------------------------------------------------------------------
    # Character State Operations
    # -------------------------------------------------------------------------

    def add_character_state(self, beat_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Add a character state to a plot beat.

        Args:
            beat_id: Beat UUID string.
            state: Character state with keys:
                - character_name (required): Name of the character
                - emotional_state (optional): Emotional state description
                - dialogue_context (optional): Dialogue context
                - physical_action (optional): Physical action description
                - embedding (optional): Vector embedding

        Returns:
            Created character state as dict.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        embedding = state.get("embedding")
        if embedding is not None:
            embedding = np.array(embedding).tolist()

        cursor.execute(
            """
            INSERT INTO character_states (beat_id, character_name, emotional_state,
                                         dialogue_context, physical_action, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, beat_id, character_name, emotional_state, dialogue_context,
                     physical_action, embedding, created_at
            """,
            (
                beat_id,
                state["character_name"],
                state.get("emotional_state"),
                state.get("dialogue_context"),
                state.get("physical_action"),
                embedding,
            ),
        )

        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return self._row_to_character_state_dict(row)

    def get_character_states(self, beat_id: str) -> List[Dict[str, Any]]:
        """Get all character states for a beat.

        Args:
            beat_id: Beat UUID string.

        Returns:
            List of character state dicts.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, beat_id, character_name, emotional_state, dialogue_context,
                   physical_action, embedding, created_at
            FROM character_states
            WHERE beat_id = %s
            ORDER BY created_at ASC
            """,
            (beat_id,),
        )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_character_state_dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Consumption Record Operations
    # -------------------------------------------------------------------------

    def record_consumption(self, scene_id: str, consumer_type: str,
                          content: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record downstream content consumption.

        Args:
            scene_id: Scene UUID string.
            consumer_type: Type of consumer (novel/podcast/video/music).
            content: Generated content from consumption.
            metadata: Additional metadata about the consumption.

        Returns:
            Created consumption record as dict.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        metadata_json = None
        if metadata:
            metadata_json = json.dumps(metadata) if not isinstance(metadata, str) else metadata

        cursor.execute(
            """
            INSERT INTO consumption_records (scene_id, consumer_type, output_content, metadata)
            VALUES (%s, %s, %s, %s)
            RETURNING id, scene_id, consumer_type, output_content, status, metadata, created_at
            """,
            (scene_id, consumer_type, content, metadata_json),
        )

        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return self._row_to_consumption_dict(row)

    def get_consumption_records(self, scene_id: str) -> List[Dict[str, Any]]:
        """Get all consumption records for a scene.

        Args:
            scene_id: Scene UUID string.

        Returns:
            List of consumption record dicts.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, scene_id, consumer_type, output_content, status, metadata, created_at
            FROM consumption_records
            WHERE scene_id = %s
            ORDER BY created_at DESC
            """,
            (scene_id,),
        )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_consumption_dict(row) for row in rows]

    def update_consumption_status(self, record_id: str, status: str,
                                 output_content: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update consumption record status.

        Args:
            record_id: Record UUID string.
            status: New status.
            output_content: Updated content if provided.

        Returns:
            Updated record dict or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if output_content is not None:
            cursor.execute(
                """
                UPDATE consumption_records
                SET status = %s, output_content = %s
                WHERE id = %s
                RETURNING id, scene_id, consumer_type, output_content, status, metadata, created_at
                """,
                (status, output_content, record_id),
            )
        else:
            cursor.execute(
                """
                UPDATE consumption_records SET status = %s
                WHERE id = %s
                RETURNING id, scene_id, consumer_type, output_content, status, metadata, created_at
                """,
                (status, record_id),
            )

        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if row:
            return self._row_to_consumption_dict(row)
        return None

    # -------------------------------------------------------------------------
    # Complex Queries
    # -------------------------------------------------------------------------

    def get_scene_with_beats(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Get complete scene data including all beats and character states.

        Args:
            scene_id: Scene UUID string.

        Returns:
            Complete scene dict with beats array, or None if scene not found.
        """
        scene = self.get_scene(scene_id)
        if not scene:
            return None

        beats = self.get_beats_for_scene(scene_id)
        for beat in beats:
            beat["character_states"] = self.get_character_states(beat["id"])

        scene["beats"] = beats
        scene["consumption_records"] = self.get_consumption_records(scene_id)

        return scene

    def search_beats_by_similarity(self, query_embedding: List[float],
                                   top_k: int = 5) -> List[Dict[str, Any]]:
        """Search plot beats by vector similarity.

        Uses pgvector's cosine distance for similarity search.

        Args:
            query_embedding: Query vector for semantic search.
            top_k: Number of top results to return.

        Returns:
            List of beat dicts ordered by similarity (most similar first).
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        embedding = np.array(query_embedding).tolist()

        cursor.execute(
            """
            SELECT id, scene_id, beat_type, description, character_interactions,
                   scene_description, narration, sequence, embedding, created_at,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM plot_beats
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (embedding, embedding, top_k),
        )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        results = []
        for row in rows:
            beat = self._row_to_beat_dict(row)
            beat["similarity"] = float(row[-1]) if row[-1] is not None else 0.0
            results.append(beat)

        return results

    def search_character_states_by_similarity(self, query_embedding: List[float],
                                             top_k: int = 5) -> List[Dict[str, Any]]:
        """Search character states by vector similarity.

        Args:
            query_embedding: Query vector for semantic search.
            top_k: Number of top results to return.

        Returns:
            List of character state dicts ordered by similarity.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        embedding = np.array(query_embedding).tolist()

        cursor.execute(
            """
            SELECT id, beat_id, character_name, emotional_state, dialogue_context,
                   physical_action, embedding, created_at,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM character_states
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (embedding, embedding, top_k),
        )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        results = []
        for row in rows:
            state = self._row_to_character_state_dict(row)
            state["similarity"] = float(row[-1]) if row[-1] is not None else 0.0
            results.append(state)

        return results

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _row_to_scene_dict(self, row) -> Dict[str, Any]:
        """Convert database row to scene dict."""
        return {
            "id": str(row[0]),
            "chapter": row[1],
            "title": row[2],
            "background": row[3],
            "location": row[4],
            "time_of_day": row[5],
            "emotional_arc": json.loads(row[6]) if row[6] else None,
            "narration": row[7],
            "status": row[8],
            "created_at": row[9].isoformat() if hasattr(row[9], 'isoformat') else row[9],
            "updated_at": row[10].isoformat() if hasattr(row[10], 'isoformat') else row[10],
        }

    def _row_to_beat_dict(self, row) -> Dict[str, Any]:
        """Convert database row to plot beat dict."""
        embedding = row[8]
        if embedding is not None:
            embedding = list(embedding) if not isinstance(embedding, list) else embedding

        return {
            "id": str(row[0]),
            "scene_id": str(row[1]),
            "beat_type": row[2],
            "description": row[3],
            "character_interactions": json.loads(row[4]) if row[4] else None,
            "scene_description": row[5],
            "narration": row[6],
            "sequence": row[7],
            "embedding": embedding,
            "created_at": row[9].isoformat() if hasattr(row[9], 'isoformat') else row[9],
        }

    def _row_to_character_state_dict(self, row) -> Dict[str, Any]:
        """Convert database row to character state dict."""
        embedding = row[6]
        if embedding is not None:
            embedding = list(embedding) if not isinstance(embedding, list) else embedding

        return {
            "id": str(row[0]),
            "beat_id": str(row[1]),
            "character_name": row[2],
            "emotional_state": row[3],
            "dialogue_context": row[4],
            "physical_action": row[5],
            "embedding": embedding,
            "created_at": row[7].isoformat() if hasattr(row[7], 'isoformat') else row[7],
        }

    def _row_to_consumption_dict(self, row) -> Dict[str, Any]:
        """Convert database row to consumption record dict."""
        return {
            "id": str(row[0]),
            "scene_id": str(row[1]),
            "consumer_type": row[2],
            "output_content": row[3],
            "status": row[4],
            "metadata": json.loads(row[5]) if row[5] else None,
            "created_at": row[6].isoformat() if hasattr(row[6], 'isoformat') else row[6],
        }


# -----------------------------------------------------------------------------
# Singleton pattern for convenience
# -----------------------------------------------------------------------------

_store: Optional[SceneStore] = None


def get_scene_store(database_url: Optional[str] = None) -> SceneStore:
    """Get SceneStore singleton instance.

    Args:
        database_url: Optional database URL override.

    Returns:
        SceneStore instance.
    """
    global _store
    if _store is None or database_url is not None:
        _store = SceneStore(database_url)
    return _store
