"""Service for generating and managing embeddings for experts and queries"""

import logging
from typing import Any

from groupchat.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using OpenAI"""

    def __init__(self):
        self.model = "text-embedding-3-small"  # Cost-effective and good performance

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for given text"""
        if settings.enable_real_embeddings and settings.openai_api_key:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
                
                logger.info(f"Generating OpenAI embedding for text: '{text[:50]}...'")
                response = await client.embeddings.create(
                    model=self.model,
                    input=text
                )
                
                embedding = response.data[0].embedding
                logger.debug(f"Generated OpenAI embedding of length {len(embedding)}")
                return embedding
                
            except Exception as e:
                logger.error(f"Failed to generate OpenAI embedding: {e}")
                logger.info("Falling back to mock embedding")
                return self._generate_mock_embedding(text)
        else:
            logger.info("Real embeddings disabled, using mock embedding")
            return self._generate_mock_embedding(text)

    def _generate_mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding for testing"""
        import random
        random.seed(hash(text))  # Deterministic for testing
        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        logger.debug(f"Generated mock embedding of length {len(embedding)}")
        return embedding

    async def generate_expertise_embedding(self, expertise_summary: str, bio: str = "") -> list[float]:
        """Generate embedding for expert's expertise combining summary and bio"""
        # Combine expertise summary and bio for better context
        combined_text = f"Expertise: {expertise_summary}"
        if bio:
            combined_text += f" Biography: {bio}"
        
        return await self.generate_embedding(combined_text)

    async def batch_generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        import math
        
        # Calculate dot product
        dot_product = sum(x * y for x, y in zip(a, b))
        
        # Calculate magnitudes
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))
        
        # Avoid division by zero
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)

    def format_for_pgvector(self, embedding: list[float]) -> str:
        """Format embedding for PostgreSQL pgvector storage"""
        return f"[{','.join(map(str, embedding))}]"