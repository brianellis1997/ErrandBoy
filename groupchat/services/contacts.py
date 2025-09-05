"""Contact management business logic and database operations"""

import logging
from datetime import datetime
from uuid import UUID, uuid4

import openai
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from groupchat.config import settings
from groupchat.db.models import Contact, ContactExpertise, ContactStatus, ExpertiseTag
from groupchat.schemas.contacts import (
    AddExpertiseRequest,
    ContactCreate,
    ContactSearchRequest,
    ContactUpdate,
)

logger = logging.getLogger(__name__)


class ContactService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_contact(self, contact_data: ContactCreate) -> Contact:
        """Create a new contact with expertise tags"""

        existing_contact = await self._get_contact_by_phone(contact_data.phone_number)
        if existing_contact and not existing_contact.is_deleted:
            raise ValueError("Contact with this phone number already exists")

        if contact_data.email:
            existing_email = await self._get_contact_by_email(contact_data.email)
            if existing_email and not existing_email.is_deleted:
                raise ValueError("Contact with this email already exists")

        contact = Contact(
            id=uuid4(),
            phone_number=contact_data.phone_number,
            email=contact_data.email,
            name=contact_data.name,
            bio=contact_data.bio,
            is_available=contact_data.is_available,
            max_queries_per_day=contact_data.max_queries_per_day,
            preferred_contact_method=contact_data.preferred_contact_method,
            status=ContactStatus.PENDING,
            extra_metadata=contact_data.extra_metadata,
        )

        if (
            contact_data.bio
            and settings.enable_real_embeddings
            and settings.openai_api_key
        ):
            try:
                embedding = await self._generate_embedding(contact_data.bio)
                contact.expertise_embedding = embedding
                contact.expertise_summary = contact_data.bio[:500]
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        self.db.add(contact)
        await self.db.flush()

        if contact_data.expertise_tags:
            await self._add_expertise_tags(contact.id, contact_data.expertise_tags)

        await self.db.refresh(contact)
        return contact

    async def get_contact(self, contact_id: UUID) -> Contact | None:
        """Get contact by ID including expertise tags"""
        query = (
            select(Contact)
            .where(and_(Contact.id == contact_id, Contact.deleted_at.is_(None)))
            .options(selectinload(Contact.expertise_tags))
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_contact_by_phone(self, phone_number: str) -> Contact | None:
        """Get contact by phone number"""
        return await self._get_contact_by_phone(phone_number)

    async def update_contact(
        self, contact_id: UUID, update_data: ContactUpdate
    ) -> Contact | None:
        """Update contact information"""
        contact = await self.get_contact(contact_id)
        if not contact:
            return None

        if update_data.email and update_data.email != contact.email:
            existing_email = await self._get_contact_by_email(update_data.email)
            if existing_email and existing_email.id != contact_id:
                raise ValueError("Contact with this email already exists")

        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(contact, field, value)

        contact.updated_at = datetime.utcnow()

        if (
            update_data.bio
            and settings.enable_real_embeddings
            and settings.openai_api_key
        ):
            try:
                embedding = await self._generate_embedding(update_data.bio)
                contact.expertise_embedding = embedding
                contact.expertise_summary = update_data.bio[:500]
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        await self.db.flush()
        await self.db.refresh(contact)
        return contact

    async def delete_contact(self, contact_id: UUID) -> bool:
        """Soft delete contact"""
        contact = await self.get_contact(contact_id)
        if not contact:
            return False

        contact.deleted_at = datetime.utcnow()
        contact.is_available = False
        await self.db.flush()
        return True

    async def list_contacts(
        self, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> tuple[list[Contact], int]:
        """List contacts with pagination"""
        base_query = select(Contact).options(selectinload(Contact.expertise_tags))

        if not include_deleted:
            base_query = base_query.where(Contact.deleted_at.is_(None))

        count_query = select(func.count(Contact.id))
        if not include_deleted:
            count_query = count_query.where(Contact.deleted_at.is_(None))

        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        contacts_query = (
            base_query.offset(skip).limit(limit).order_by(Contact.created_at.desc())
        )
        contacts_result = await self.db.execute(contacts_query)
        contacts = contacts_result.scalars().all()

        return list(contacts), total

    async def search_contacts(
        self, search_request: ContactSearchRequest
    ) -> tuple[list[Contact], int]:
        """Search contacts by various criteria"""
        base_query = (
            select(Contact)
            .options(selectinload(Contact.expertise_tags))
            .where(Contact.deleted_at.is_(None))
        )

        if search_request.available_only:
            base_query = base_query.where(
                and_(Contact.is_available, Contact.status == ContactStatus.ACTIVE)
            )

        if search_request.min_trust_score:
            base_query = base_query.where(
                Contact.trust_score >= search_request.min_trust_score
            )

        if search_request.max_response_time_minutes:
            base_query = base_query.where(
                or_(
                    Contact.avg_response_time_minutes.is_(None),
                    Contact.avg_response_time_minutes
                    <= search_request.max_response_time_minutes,
                )
            )

        if search_request.expertise_tags:
            base_query = (
                base_query.join(ContactExpertise)
                .join(ExpertiseTag)
                .where(ExpertiseTag.name.in_(search_request.expertise_tags))
            )

        if search_request.query and search_request.query.strip():
            search_term = f"%{search_request.query.strip()}%"
            base_query = base_query.where(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.bio.ilike(search_term),
                    Contact.expertise_summary.ilike(search_term),
                )
            )

        count_query = select(func.count(Contact.id.distinct())).select_from(
            base_query.subquery()
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        contacts_query = (
            base_query.offset(search_request.skip)
            .limit(search_request.limit)
            .order_by(Contact.trust_score.desc(), Contact.response_rate.desc())
        )
        contacts_result = await self.db.execute(contacts_query)
        contacts = contacts_result.scalars().unique().all()

        return list(contacts), total

    async def add_expertise_to_contact(
        self, contact_id: UUID, expertise_request: AddExpertiseRequest
    ) -> Contact:
        """Add expertise tags to a contact"""
        contact = await self.get_contact(contact_id)
        if not contact:
            raise ValueError("Contact not found")

        await self._add_expertise_tags(
            contact_id,
            expertise_request.expertise_tags,
            expertise_request.confidence_scores,
        )

        await self.db.refresh(contact)
        return contact

    async def _get_contact_by_phone(self, phone_number: str) -> Contact | None:
        """Helper to get contact by phone number"""
        query = select(Contact).where(Contact.phone_number == phone_number)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_contact_by_email(self, email: str) -> Contact | None:
        """Helper to get contact by email"""
        query = select(Contact).where(Contact.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _add_expertise_tags(
        self,
        contact_id: UUID,
        tag_names: list[str],
        confidence_scores: list[float] | None = None,
    ) -> None:
        """Add expertise tags to contact"""
        for i, tag_name in enumerate(tag_names):
            tag = await self._get_or_create_expertise_tag(tag_name)
            confidence = confidence_scores[i] if confidence_scores else 1.0

            existing_query = select(ContactExpertise).where(
                and_(
                    ContactExpertise.contact_id == contact_id,
                    ContactExpertise.tag_id == tag.id,
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if not existing:
                contact_expertise = ContactExpertise(
                    contact_id=contact_id, tag_id=tag.id, confidence_score=confidence
                )
                self.db.add(contact_expertise)

    async def _get_or_create_expertise_tag(self, tag_name: str) -> ExpertiseTag:
        """Get existing expertise tag or create new one"""
        query = select(ExpertiseTag).where(
            ExpertiseTag.name == tag_name.lower().strip()
        )
        result = await self.db.execute(query)
        tag = result.scalar_one_or_none()

        if not tag:
            tag = ExpertiseTag(
                id=uuid4(),
                name=tag_name.lower().strip(),
                description=f"Expertise in {tag_name}",
            )
            self.db.add(tag)
            await self.db.flush()

        return tag

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using OpenAI API"""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.embeddings.create(
            model="text-embedding-ada-002", input=text[:8000]
        )

        return response.data[0].embedding
