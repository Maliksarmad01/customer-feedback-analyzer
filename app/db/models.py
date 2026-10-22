
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False)
    sentiment = Column(String(20), nullable=False)
    product_feature = Column(String(100), nullable=False)
    suggested_reply = Column(Text, nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="open",
        server_default="open",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TicketActivity(Base):
    __tablename__ = "ticket_activities"

    id = Column(Integer, primary_key=True, index=True)

    # No foreign key: activity history survives ticket deletion.
    ticket_id = Column(Integer, nullable=False, index=True)
    related_ticket_id = Column(Integer, nullable=True, index=True)

    action = Column(String(30), nullable=False)
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)

    ticket_snapshot = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    actor = Column(String(100), nullable=False, default="system")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
