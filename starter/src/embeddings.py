"""Choose a real embedding provider (OpenAI) and implement embedder contract."""
import os
from pathlib import Path
from typing import Protocol
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from starter directory or current directory
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Real embedding provider adapter using OpenAI text-embedding-3-small."""

    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY missing in environment or starter/.env! "
                "Per lab rules, fallback to random mock vectors is prohibited."
            )

        self.model_name = (
            model_name
            or os.getenv("EMBEDDING_MODEL")
            or "text-embedding-3-small"
        )
        self.dimensions = 1536  # text-embedding-3-small default dimensions
        self.client = OpenAI(api_key=api_key)
        self.total_tokens_used = 0
        self.cost_per_million_tokens = 0.02  # $0.02 per 1M tokens

    def embed_documents(
        self, texts: list[str], batch_size: int = 64
    ) -> list[list[float]]:
        """Embed a list of documents in batches with token usage tracking."""
        if not texts:
            return []

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Replace empty strings with a single space to avoid API validation errors
            clean_batch = [t if t.strip() else " " for t in batch]

            response = self.client.embeddings.create(
                input=clean_batch,
                model=self.model_name,
            )

            # Accumulate token usage
            if response.usage:
                self.total_tokens_used += response.usage.total_tokens

            # Extract vectors in proper order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            for item in sorted_data:
                vec = item.embedding
                if len(vec) != self.dimensions:
                    self.dimensions = len(vec)
                all_vectors.append(vec)

        return all_vectors

    def embed_query(self, question: str) -> list[float]:
        """Embed a single search query."""
        if not question.strip():
            question = " "

        response = self.client.embeddings.create(
            input=[question],
            model=self.model_name,
        )

        if response.usage:
            self.total_tokens_used += response.usage.total_tokens

        return response.data[0].embedding

    def get_estimated_cost_usd(self) -> float:
        """Calculate total USD spent on embeddings so far."""
        return (self.total_tokens_used / 1_000_000) * self.cost_per_million_tokens
