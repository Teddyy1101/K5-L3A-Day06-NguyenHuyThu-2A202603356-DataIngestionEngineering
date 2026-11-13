"""Store and search vectors using PostgreSQL + pgvector with idempotency and metadata filtering."""
import json
from typing import Any
import psycopg
from psycopg.rows import dict_row

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int = 1536) -> None:
        self.database_url = database_url
        self.dimensions = dimensions

    def get_connection(self) -> psycopg.Connection:
        """Create a new PostgreSQL connection with autocommit disabled."""
        return psycopg.connect(self.database_url, connect_timeout=10)

    def create_schema(self) -> None:
        """Create extension and chunks table with metadata and vector column."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS chunks (
                        strategy VARCHAR(10) NOT NULL,
                        chunk_id VARCHAR(100) NOT NULL,
                        document_id VARCHAR(50) NOT NULL,
                        source VARCHAR(255) NOT NULL,
                        page INT NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({self.dimensions}) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (strategy, chunk_id)
                    );
                    """
                )
                # Create indexes for fast filtering and search
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunks_strategy 
                    ON chunks (strategy);
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunks_metadata 
                    ON chunks USING gin (metadata);
                    """
                )
            conn.commit()

    def upsert(
        self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> int:
        """Validate lengths and write stable IDs without duplicates (idempotent).

        If source chunks changed, existing chunks for that strategy and document are refreshed.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks vs {len(vectors)} vectors"
            )
        if not chunks:
            return 0

        # Validate vector dimensions
        for i, vec in enumerate(vectors):
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"Vector at index {i} has dimension {len(vec)}, expected {self.dimensions}"
                )

        # Prepare parameters for batch insert/update
        records = []
        doc_ids = set()
        for chunk, vec in zip(chunks, vectors):
            doc_ids.add(chunk.document_id)
            records.append(
                (
                    strategy,
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.source,
                    chunk.page,
                    chunk.text,
                    json.dumps(chunk.metadata),
                    vec,  # psycopg handles list of floats to pgvector
                )
            )

        query = """
            INSERT INTO chunks (
                strategy, chunk_id, document_id, source, page, text, metadata, embedding
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector
            )
            ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                source = EXCLUDED.source,
                page = EXCLUDED.page,
                text = EXCLUDED.text,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                created_at = CURRENT_TIMESTAMP;
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Remove obsolete chunks for this document in this strategy if re-ingesting
                new_chunk_ids = [c.chunk_id for c in chunks]
                cur.execute(
                    """
                    DELETE FROM chunks 
                    WHERE strategy = %s 
                      AND document_id = ANY(%s) 
                      AND chunk_id != ALL(%s);
                    """,
                    (strategy, list(doc_ids), new_chunk_ids),
                )
                cur.executemany(query, records)
            conn.commit()

        return len(records)

    def count_chunks(self, strategy: str | None = None) -> int:
        """Count total chunks currently in the store, optionally filtered by strategy."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if strategy:
                    cur.execute(
                        "SELECT COUNT(*) FROM chunks WHERE strategy = %s;",
                        (strategy,),
                    )
                else:
                    cur.execute("SELECT COUNT(*) FROM chunks;")
                row = cur.fetchone()
                return row[0] if row else 0

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter metadata in SQL, rank by cosine distance (<=>), return top-k.

        Distance ranges [0, 2]; cosine similarity = 1 - distance.
        """
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Query vector dimension {len(query_vector)} != {self.dimensions}"
            )

        where_clauses = ["strategy = %(strategy)s"]
        params: dict[str, Any] = {
            "strategy": strategy,
            "query_vec": query_vector,
            "top_k": top_k,
        }

        # Apply metadata filter (JSONB containment) when specified
        if filters:
            where_clauses.append("metadata @> %(filters)s::jsonb")
            params["filters"] = json.dumps(filters)

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                chunk_id,
                document_id,
                source,
                page,
                text,
                metadata,
                (embedding <=> %(query_vec)s::vector) AS distance,
                1 - (embedding <=> %(query_vec)s::vector) AS score
            FROM chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %(query_vec)s::vector ASC
            LIMIT %(top_k)s;
        """

        with self.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "source": r["source"],
                "page": r["page"],
                "text": r["text"],
                "metadata": r["metadata"],
                "distance": float(r["distance"]),
                "score": float(r["score"]),
            })

        return results
