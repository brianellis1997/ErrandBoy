"""Answer synthesis service for combining expert contributions"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import (
    Citation,
    CompiledAnswer,
    Contact,
    Contribution,
    Query,
    QueryStatus,
)

logger = logging.getLogger(__name__)


class SynthesisService:
    """Service for synthesizing expert contributions into coherent answers"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.openai_client = None
        # Disable OpenAI client for MVP/demo
        # if settings.openai_api_key:
        #     self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def synthesize_answer(
        self,
        query_id: uuid.UUID,
        custom_prompt: str | None = None
    ) -> CompiledAnswer:
        """
        Synthesize contributions into a single answer with citations

        Args:
            query_id: The query to synthesize
            custom_prompt: Optional custom synthesis prompt

        Returns:
            CompiledAnswer object with citations
        """
        # Get query and validate status
        query = await self._get_query_with_contributions(query_id)
        if not query:
            raise ValueError(f"Query {query_id} not found")

        if query.status not in [QueryStatus.COLLECTING, QueryStatus.COMPILING]:
            raise ValueError(
                f"Cannot synthesize query in {query.status.value} status. "
                f"Must be in COLLECTING or COMPILING status."
            )

        # Update status to COMPILING
        if query.status == QueryStatus.COLLECTING:
            await self._update_query_status(query_id, QueryStatus.COMPILING)

        try:
            # Get all contributions with contributor information
            contributions = await self._get_contributions_with_contacts(query_id)

            if not contributions:
                raise ValueError(f"No contributions found for query {query_id}")

            # Generate unique handles for each contributor
            handle_mapping = self._generate_citation_handles(contributions)

            # Prepare synthesis prompt
            prompt = custom_prompt or self._build_synthesis_prompt(
                query.question_text,
                contributions,
                handle_mapping
            )

            # Call LLM for synthesis
            synthesis_result = await self._call_llm_for_synthesis(prompt)

            # Extract citations from the synthesized answer
            citations_data = self._extract_citations(
                synthesis_result["answer"],
                handle_mapping,
                contributions
            )

            # Calculate contribution weights
            weights = self._calculate_contribution_weights(citations_data)

            # Create compiled answer
            compiled_answer = await self._create_compiled_answer(
                query_id=query_id,
                final_answer=synthesis_result["answer"],
                summary=synthesis_result.get("summary"),
                confidence_score=synthesis_result.get("confidence", 0.85),
                compilation_method="gpt-4",
                compilation_prompt=prompt,
                compilation_tokens_used=synthesis_result.get("tokens_used", 0)
            )

            # Create citation records
            await self._create_citations(
                compiled_answer.id,
                citations_data,
                weights
            )

            # Mark contributions as used
            await self._mark_contributions_used(contributions, weights)

            # Update query status to COMPLETED
            await self._update_query_status(query_id, QueryStatus.COMPLETED)

            # Process micropayment after successful synthesis
            await self._process_micropayment(query_id, compiled_answer.id)

            # Refresh and return the compiled answer with citations
            await self.db.refresh(compiled_answer)
            return compiled_answer

        except Exception as e:
            # Update query status to FAILED on error
            await self._update_query_status(
                query_id,
                QueryStatus.FAILED,
                error_message=str(e)
            )
            logger.error(f"Failed to synthesize answer for query {query_id}: {e}")
            raise

    def _generate_citation_handles(
        self,
        contributions: list[tuple[Contribution, Contact | None]]
    ) -> dict[str, tuple[Contribution, Contact | None]]:
        """Generate unique citation handles for each contributor"""
        handle_mapping = {}
        used_handles = set()

        for contribution, contact in contributions:
            if contact:
                # Generate handle from contact name
                base_handle = self._create_handle_from_name(contact.name)
                handle = base_handle
                counter = 1

                # Ensure uniqueness
                while handle in used_handles:
                    handle = f"{base_handle}{counter}"
                    counter += 1

                used_handles.add(handle)
                handle_mapping[handle] = (contribution, contact)
            else:
                # Anonymous contributor
                handle = f"anon{len(handle_mapping) + 1}"
                handle_mapping[handle] = (contribution, None)

        return handle_mapping

    def _create_handle_from_name(self, name: str) -> str:
        """Create a citation handle from a name"""
        # Remove special characters and split words
        words = re.sub(r'[^a-zA-Z\s]', '', name).split()

        if not words:
            return "user"

        if len(words) == 1:
            # Single word - use first 6 letters
            return words[0][:6].lower()
        else:
            # Multiple words - use first letter of each word + last name initial
            handle = ''.join(w[0].lower() for w in words[:-1])
            handle += words[-1][:3].lower()
            return handle

    def _build_synthesis_prompt(
        self,
        question: str,
        contributions: list[tuple[Contribution, Contact | None]],
        handle_mapping: dict[str, tuple[Contribution, Contact | None]]
    ) -> str:
        """Build the prompt for LLM synthesis"""

        # Create contribution text with handles
        contribution_texts = []
        for handle, (contribution, contact) in handle_mapping.items():
            if contact:
                expertise = contact.expertise_summary or 'Expert'
                contact_info = f"{contact.name} ({expertise})"
            else:
                contact_info = "Anonymous"
            contribution_texts.append(
                f"[@{handle}] - {contact_info}:\n{contribution.response_text}"
            )

        contributions_formatted = "\n\n".join(contribution_texts)

        prompt = f"""You are an AI assistant tasked with synthesizing multiple expert \
contributions into a single, coherent answer.

QUESTION: {question}

EXPERT CONTRIBUTIONS:
{contributions_formatted}

INSTRUCTIONS:
1. Synthesize the contributions into a comprehensive, well-structured answer
2. Use inline citations in the format [@handle] to attribute information to \
specific contributors
3. Every significant claim or piece of information MUST have a citation
4. Combine similar points from multiple experts with multiple citations like \
[@alice] [@bob]
5. Maintain factual accuracy - only include information provided by the experts
6. Create a natural, flowing answer that reads coherently
7. If experts disagree, present multiple viewpoints with appropriate citations

Return your response as a JSON object with the following structure:
{{
    "answer": "The synthesized answer with inline [@handle] citations",
    "summary": "A brief 1-2 sentence summary of the answer",
    "confidence": 0.0-1.0 confidence score based on expert agreement and coverage,
    "key_insights": ["insight1", "insight2", ...] (optional list of key takeaways)
}}

Remember: Every factual claim must have at least one citation. Be comprehensive \
but concise."""

        return prompt

    async def _call_llm_for_synthesis(self, prompt: str) -> dict[str, Any]:
        """Call OpenAI GPT-4 for answer synthesis"""

        if not self.openai_client:
            # Fallback to mock synthesis if no API key
            logger.warning("No OpenAI API key configured, using mock synthesis")
            return self._mock_synthesis_response(prompt)

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at synthesizing information "
                                 "from multiple sources into coherent, well-cited answers."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            # Parse JSON response
            result = json.loads(response.choices[0].message.content)

            # Add token usage
            result["tokens_used"] = response.usage.total_tokens if response.usage else 0

            return result

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            # Fallback to mock response
            return self._mock_synthesis_response(prompt)

    def _mock_synthesis_response(self, prompt: str) -> dict[str, Any]:
        """Generate a mock synthesis response for testing"""

        # Extract handles from the prompt
        handles = re.findall(r'\[@(\w+)\]', prompt)

        if not handles:
            handles = ["expert1", "expert2"]

        # Create a mock answer using the handles
        mock_citations = ' '.join(f'[@{h}]' for h in handles[:3])

        answer_parts = [
            f"Based on the expert contributions {mock_citations}, "
            "the answer to your question involves multiple factors.",
            f"The primary consideration mentioned by [@{handles[0]}] is "
            "the importance of the topic at hand.",
            f"Additionally, [@{handles[-1]}] provides valuable context that "
            "helps understand the broader implications.",
            "Taking all expert opinions into account, the consensus suggests "
            "a comprehensive approach is needed."
        ]
        
        return {
            "answer": " ".join(answer_parts),
            "summary": "Expert consensus indicates a multi-faceted solution "
                      "is required.",
            "confidence": 0.75,
            "key_insights": [
                "Multiple perspectives contribute to understanding",
                "Expert agreement on core principles"
            ],
            "tokens_used": 150
        }

    def _extract_citations(
        self,
        answer_text: str,
        handle_mapping: dict[str, tuple[Contribution, Contact | None]],
        contributions: list[tuple[Contribution, Contact | None]]
    ) -> list[dict[str, Any]]:
        """Extract citations from synthesized answer"""

        citations_data = []
        citation_pattern = re.compile(r'\[@(\w+)\]')

        # Find all citations in the answer
        matches = list(citation_pattern.finditer(answer_text))

        for position, match in enumerate(matches):
            handle = match.group(1)

            if handle in handle_mapping:
                contribution, contact = handle_mapping[handle]

                # Extract surrounding context for the claim
                start = max(0, match.start() - 100)
                end = min(len(answer_text), match.end() + 100)
                # claim_context = answer_text[start:end].strip()  # Not used currently

                # Clean up the claim text
                claim_text = self._extract_claim_text(answer_text, match.start())

                citations_data.append({
                    "contribution_id": contribution.id,
                    "contact_id": contact.id if contact else None,
                    "handle": handle,
                    "claim_text": claim_text,
                    "source_excerpt": contribution.response_text[:200],
                    "position": position,
                    "confidence": contribution.confidence_score
                })

        return citations_data

    def _extract_claim_text(self, answer_text: str, citation_pos: int) -> str:
        """Extract the claim text around a citation"""

        # Find sentence boundaries
        sentences = re.split(r'[.!?]\s+', answer_text)

        current_pos = 0
        for sentence in sentences:
            sentence_end = current_pos + len(sentence)
            if current_pos <= citation_pos <= sentence_end:
                # Citation is in this sentence
                return sentence.strip()
            current_pos = sentence_end + 2  # Account for delimiter

        # Fallback: extract ~50 chars around citation
        start = max(0, citation_pos - 50)
        end = min(len(answer_text), citation_pos + 50)
        return answer_text[start:end].strip()

    def _calculate_contribution_weights(
        self,
        citations_data: list[dict[str, Any]]
    ) -> dict[uuid.UUID, float]:
        """Calculate contribution weights based on citation frequency"""

        # Count citations per contribution
        citation_counts = {}
        for citation in citations_data:
            contrib_id = citation["contribution_id"]
            citation_counts[contrib_id] = citation_counts.get(contrib_id, 0) + 1

        # Calculate total citations
        total_citations = sum(citation_counts.values())

        if total_citations == 0:
            return {}

        # Calculate weights (proportional to citation frequency)
        weights = {}
        for contrib_id, count in citation_counts.items():
            weights[contrib_id] = count / total_citations

        # Ensure weights sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        return weights

    async def _get_query_with_contributions(self, query_id: uuid.UUID) -> Query | None:
        """Get query with contributions loaded"""
        stmt = select(Query).where(Query.id == query_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_contributions_with_contacts(
        self,
        query_id: uuid.UUID
    ) -> list[tuple[Contribution, Contact | None]]:
        """Get contributions with associated contact information"""

        stmt = (
            select(Contribution, Contact)
            .outerjoin(Contact, Contribution.contact_id == Contact.id)
            .where(Contribution.query_id == query_id)
            .where(Contribution.responded_at.isnot(None))
            .order_by(Contribution.confidence_score.desc())
        )

        result = await self.db.execute(stmt)
        return result.all()

    async def _create_compiled_answer(
        self,
        query_id: uuid.UUID,
        final_answer: str,
        summary: str | None,
        confidence_score: float,
        compilation_method: str,
        compilation_prompt: str,
        compilation_tokens_used: int
    ) -> CompiledAnswer:
        """Create a compiled answer record"""

        compiled_answer = CompiledAnswer(
            id=uuid.uuid4(),
            query_id=query_id,
            final_answer=final_answer,
            summary=summary,
            confidence_score=confidence_score,
            compilation_method=compilation_method,
            compilation_prompt=compilation_prompt,
            compilation_tokens_used=compilation_tokens_used,
            extra_metadata={}
        )

        self.db.add(compiled_answer)
        await self.db.commit()

        return compiled_answer

    async def _create_citations(
        self,
        compiled_answer_id: uuid.UUID,
        citations_data: list[dict[str, Any]],
        weights: dict[uuid.UUID, float]
    ) -> None:
        """Create citation records"""

        for citation_data in citations_data:
            citation = Citation(
                id=uuid.uuid4(),
                compiled_answer_id=compiled_answer_id,
                contribution_id=citation_data["contribution_id"],
                claim_text=citation_data["claim_text"],
                source_excerpt=citation_data["source_excerpt"],
                position_in_answer=citation_data["position"],
                confidence=citation_data["confidence"]
            )
            self.db.add(citation)

        await self.db.commit()

    async def _mark_contributions_used(
        self,
        contributions: list[tuple[Contribution, Contact | None]],
        weights: dict[uuid.UUID, float]
    ) -> None:
        """Mark contributions as used and set their weights"""

        for contribution, _ in contributions:
            contribution.was_used = contribution.id in weights

            # Calculate payout based on weight (simplified)
            if contribution.id in weights:
                # Assuming total payout pool is set elsewhere
                # This is a placeholder calculation
                contribution.relevance_score = weights[contribution.id]

        await self.db.commit()

    async def _update_query_status(
        self,
        query_id: uuid.UUID,
        status: QueryStatus,
        error_message: str | None = None
    ) -> None:
        """Update query status"""

        stmt = select(Query).where(Query.id == query_id)
        result = await self.db.execute(stmt)
        query = result.scalar_one_or_none()

        if query:
            query.status = status
            if error_message:
                query.error_message = error_message
            query.updated_at = datetime.utcnow()
            await self.db.commit()

    async def get_synthesis_status(self, query_id: uuid.UUID) -> dict[str, Any]:
        """Get the current synthesis status for a query"""

        # Check if compiled answer exists
        stmt = select(CompiledAnswer).where(CompiledAnswer.query_id == query_id)
        result = await self.db.execute(stmt)
        compiled_answer = result.scalar_one_or_none()

        if compiled_answer:
            # Count citations
            citation_stmt = select(Citation).where(
                Citation.compiled_answer_id == compiled_answer.id
            )
            citation_result = await self.db.execute(citation_stmt)
            citations = citation_result.scalars().all()

            return {
                "synthesized": True,
                "answer_id": compiled_answer.id,
                "confidence_score": compiled_answer.confidence_score,
                "citation_count": len(citations),
                "synthesis_method": compiled_answer.compilation_method,
                "tokens_used": compiled_answer.compilation_tokens_used
            }

        return {
            "synthesized": False,
            "answer_id": None,
            "confidence_score": 0.0,
            "citation_count": 0,
            "synthesis_method": None,
            "tokens_used": 0
        }

    async def _process_micropayment(
        self,
        query_id: uuid.UUID,
        compiled_answer_id: uuid.UUID
    ) -> None:
        """Process micropayment for completed synthesis"""
        
        try:
            # Import here to avoid circular imports
            from groupchat.services.ledger import LedgerService
            
            ledger_service = LedgerService(self.db)
            result = await ledger_service.process_query_payment(
                query_id=query_id,
                compiled_answer_id=compiled_answer_id
            )
            
            if result["success"]:
                logger.info(
                    f"Processed micropayment for query {query_id}: "
                    f"${result['total_amount_cents']/100:.4f} split among "
                    f"{result['contributors_paid']} contributors"
                )
            else:
                logger.warning(
                    f"Micropayment processing failed for query {query_id}: "
                    f"{result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            # Log error but don't fail synthesis - payments can be processed later
            logger.error(
                f"Error processing micropayment for query {query_id}: {e}",
                exc_info=True
            )
