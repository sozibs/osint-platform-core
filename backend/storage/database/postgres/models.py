"""
SQLAlchemy 2.0 ORM models for the OSINT Platform.

All models use:
- UUID primary keys generated server-side via gen_random_uuid()
- JSONB columns for flexible structured data (PostgreSQL-native)
- server_default timestamps to avoid application-clock drift
- Mapped / mapped_column syntax (SQLAlchemy 2.0)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.database.postgres import Base


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    created_cases: Mapped[list["Case"]] = relationship(
        "Case", foreign_keys="Case.created_by", back_populates="creator"
    )
    assigned_cases: Mapped[list["Case"]] = relationship(
        "Case", foreign_keys="Case.assigned_to", back_populates="assignee"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"


# ── API Keys ──────────────────────────────────────────────────────────────────

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permissions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_user_id_is_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} name={self.name!r} user_id={self.user_id}>"


# ── Sources ───────────────────────────────────────────────────────────────────

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # api | rss | web | file
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    legal_status: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="unverified"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    entity_sources: Mapped[list["EntitySource"]] = relationship(
        "EntitySource", back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.name!r} type={self.source_type!r}>"


# ── Entities ──────────────────────────────────────────────────────────────────

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # person | organization | location | ip | domain | email | phone |
    # url | hash | cryptocurrency | vehicle | document
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    aliases: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=list)
    attributes: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    canonical_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Self-referential alias resolution
    canonical: Mapped[Optional["Entity"]] = relationship(
        "Entity", remote_side="Entity.id", foreign_keys=[canonical_id]
    )
    entity_sources: Mapped[list["EntitySource"]] = relationship(
        "EntitySource", back_populates="entity", cascade="all, delete-orphan"
    )
    outgoing_relationships: Mapped[list["Relationship"]] = relationship(
        "Relationship",
        foreign_keys="Relationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["Relationship"]] = relationship(
        "Relationship",
        foreign_keys="Relationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )
    case_entities: Mapped[list["CaseEntity"]] = relationship(
        "CaseEntity", back_populates="entity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_entities_type_name", "entity_type", "name"),
        Index("ix_entities_confidence", "confidence_score"),
        Index("ix_entities_is_canonical", "is_canonical"),
    )

    def __repr__(self) -> str:
        return (
            f"<Entity id={self.id} type={self.entity_type!r} name={self.name!r}>"
        )


# ── Relationships ─────────────────────────────────────────────────────────────

class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attributes: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    is_directed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )

    source_entity: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[source_entity_id], back_populates="outgoing_relationships"
    )
    target_entity: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[target_entity_id], back_populates="incoming_relationships"
    )

    __table_args__ = (
        Index("ix_relationships_source_target", "source_entity_id", "target_entity_id"),
        Index("ix_relationships_type", "relationship_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Relationship id={self.id} type={self.relationship_type!r} "
            f"src={self.source_entity_id} -> tgt={self.target_entity_id}>"
        )


# ── Entity Sources ────────────────────────────────────────────────────────────

class EntitySource(Base):
    __tablename__ = "entity_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")

    entity: Mapped["Entity"] = relationship("Entity", back_populates="entity_sources")
    source: Mapped["Source"] = relationship("Source", back_populates="entity_sources")

    __table_args__ = (
        Index("ix_entity_sources_entity_source", "entity_id", "source_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EntitySource id={self.id} entity_id={self.entity_id} source_id={self.source_id}>"
        )


# ── Cases ─────────────────────────────────────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="open", index=True
    )  # open | closed | archived
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="medium", index=True
    )  # low | medium | high | critical
    tags: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], back_populates="created_cases"
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_to], back_populates="assigned_cases"
    )
    case_entities: Mapped[list["CaseEntity"]] = relationship(
        "CaseEntity", back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cases_status_priority", "status", "priority"),
        Index("ix_cases_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} name={self.name!r} status={self.status!r}>"


# ── Case Entities ─────────────────────────────────────────────────────────────

class CaseEntity(Base):
    __tablename__ = "case_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="case_entities")
    entity: Mapped["Entity"] = relationship("Entity", back_populates="case_entities")

    __table_args__ = (
        Index("ix_case_entities_case_entity", "case_id", "entity_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CaseEntity case_id={self.case_id} entity_id={self.entity_id}>"


# ── Audit Logs ────────────────────────────────────────────────────────────────

class Log(Base):
    __tablename__ = "logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_logs_user_action", "user_id", "action"),
        Index("ix_logs_resource", "resource_type", "resource_id"),
        Index("ix_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Log id={self.id} action={self.action!r} "
            f"resource={self.resource_type!r}/{self.resource_id!r}>"
        )
