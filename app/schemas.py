
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketAnalyzeRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Customer feedback or support message",
    )


class TicketAnalyzeResponse(BaseModel):
    accepted: bool
    message: str = Field(min_length=1, max_length=5000)
    status: str
    reason: str

    category: Optional[str] = None
    priority: Optional[str] = None
    sentiment: Optional[str] = None
    product_feature: Optional[str] = None
    suggested_reply: Optional[str] = None
    ticket_id: Optional[int] = None


class TicketRecord(BaseModel):
    id: int
    message: str
    category: str
    priority: str
    sentiment: str
    product_feature: str
    suggested_reply: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketListResponse(BaseModel):
    total: int
    tickets: list[TicketRecord]


class TicketStatusUpdate(BaseModel):
    status: Literal["open", "resolved"]


class AnalyticsResponse(BaseModel):
    total_tickets: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_sentiment: dict[str, int]


class BatchTicketAnalyzeRequest(BaseModel):
    messages: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Between 1 and 100 customer messages",
    )


class BatchTicketAnalyzeResponse(BaseModel):
    total_submitted: int
    accepted_count: int
    rejected_count: int
    results: list[TicketAnalyzeResponse]


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=256)

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
