import csv
import io
import json
import os
from datetime import datetime, timezone

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    File,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.db.database import Base, engine, get_db
from app.db.models import Ticket, TicketActivity, User
from app.schemas import (
    AnalyticsResponse,
    BatchTicketAnalyzeRequest,
    BatchTicketAnalyzeResponse,
    TicketAnalyzeRequest,
    TicketAnalyzeResponse,
    TicketListResponse,
    TicketRecord,
    TicketStatusUpdate,
    SignupRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
)
from app.services.analyzer import analyze_message
from app.services.filtering import filter_message
from app.services.auth import (
    hash_password,
    verify_password,
    create_token,
    read_token,
)


# ---------------------------------------------------------
# DATABASE INITIALIZATION AND MIGRATION
# ---------------------------------------------------------

Base.metadata.create_all(bind=engine)

# Add status to existing databases without deleting data.
with engine.begin() as connection:
    table_names = inspect(connection).get_table_names()

    if "tickets" in table_names:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("tickets")
        }

        if "status" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE tickets "
                    "ADD COLUMN status VARCHAR(20) "
                    "NOT NULL DEFAULT 'open'"
                )
            )


# ---------------------------------------------------------
# FASTAPI APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="AI Customer Feedback & Support Ticket Analyzer",
    description=(
        "Analyze feedback, manage support tickets, "
        "and track ticket activity."
    ),
    version="2.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# SWAGGER / OPENAPI BEARER AUTHENTICATION
# ---------------------------------------------------------

# This registers HTTP Bearer authentication in OpenAPI,
# enabling the Authorize button in Swagger UI.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # HTTPBearer extracts the token without the "Bearer " prefix.
    token = credentials.credentials
    user_id = read_token(token)

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
        if user_id
        else None
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ---------------------------------------------------------
# AUDIT HISTORY HELPER
# ---------------------------------------------------------

def record_ticket_activity(
    db: Session,
    ticket: Ticket,
    action: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    details: str | None = None,
    related_ticket_id: int | None = None,
):
    snapshot = {
        "id": ticket.id,
        "message": ticket.message,
        "category": ticket.category,
        "priority": ticket.priority,
        "sentiment": ticket.sentiment,
        "product_feature": ticket.product_feature,
        "suggested_reply": ticket.suggested_reply,
        "status": ticket.status,
        "created_at": (
            ticket.created_at.isoformat()
            if ticket.created_at
            else None
        ),
    }

    activity = TicketActivity(
        ticket_id=ticket.id,
        related_ticket_id=related_ticket_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        ticket_snapshot=json.dumps(
            snapshot,
            ensure_ascii=False,
        ),
        details=details,
        actor="system",
        created_at=datetime.now(timezone.utc),
    )

    db.add(activity)
    return activity


def ticket_not_found(ticket_id: int):
    return HTTPException(
        status_code=404,
        detail=f"Ticket {ticket_id} not found",
    )


def _public_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
    )


# ---------------------------------------------------------
# AUTHENTICATION ROUTES
# ---------------------------------------------------------

@app.post(
    "/auth/signup",
    response_model=AuthResponse,
    status_code=201,
)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()
    name = request.name.strip()

    if (
        "@" not in email
        or email.startswith("@")
        or email.endswith("@")
    ):
        raise HTTPException(
            status_code=422,
            detail="Enter a valid email address",
        )

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Name cannot be blank",
        )

    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(request.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Could not create account; "
                "the email may already be registered"
            ),
        )

    return AuthResponse(
        access_token=create_token(user.id),
        user=_public_user(user),
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()

    user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if user is None or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    return AuthResponse(
        access_token=create_token(user.id),
        user=_public_user(user),
    )


@app.get("/auth/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)):
    return _public_user(user)


# ---------------------------------------------------------
# HOME AND HEALTH
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Customer Feedback Analyzer is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------------
# ANALYZE ONE TICKET
# ---------------------------------------------------------

@app.post(
    "/tickets/analyze",
    response_model=TicketAnalyzeResponse,
)
def analyze_ticket(
    request: TicketAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filter_result = filter_message(request.message)

    if not filter_result.is_valid:
        return TicketAnalyzeResponse(
            accepted=False,
            message=request.message,
            status="rejected",
            reason=filter_result.reason,
        )

    analysis = analyze_message(request.message)

    try:
        ticket = Ticket(
            message=request.message,
            category=analysis["category"],
            priority=analysis["priority"],
            sentiment=analysis["sentiment"],
            product_feature=analysis["product_feature"],
            suggested_reply=analysis["suggested_reply"],
            status="open",
        )

        db.add(ticket)
        db.flush()

        record_ticket_activity(
            db,
            ticket,
            action="CREATED",
            previous_status=None,
            new_status="open",
            details="Ticket created from feedback analysis",
        )

        db.commit()
        db.refresh(ticket)

        return TicketAnalyzeResponse(
            accepted=True,
            message=ticket.message,
            status="analyzed",
            reason=filter_result.reason,
            category=ticket.category,
            priority=ticket.priority,
            sentiment=ticket.sentiment,
            product_feature=ticket.product_feature,
            suggested_reply=ticket.suggested_reply,
            ticket_id=ticket.id,
        )

    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# LIST TICKETS
# ---------------------------------------------------------

@app.get("/tickets", response_model=TicketListResponse)
def get_tickets(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Ticket)

    if status is not None:
        normalized_status = status.strip().lower()

        if normalized_status not in {"open", "resolved"}:
            raise HTTPException(
                status_code=422,
                detail="Status must be 'open' or 'resolved'",
            )

        query = query.filter(
            Ticket.status == normalized_status
        )

    total = query.count()

    tickets = (
        query.order_by(Ticket.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return TicketListResponse(
        total=total,
        tickets=tickets,
    )


# ---------------------------------------------------------
# ACTIVITY HISTORY
# Keep before /tickets/{ticket_id}.
# ---------------------------------------------------------

@app.get("/tickets/activity")
@app.get("/activity")
def get_ticket_activity(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ticket_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(TicketActivity)

    if ticket_id is not None:
        query = query.filter(
            (TicketActivity.ticket_id == ticket_id)
            | (
                TicketActivity.related_ticket_id
                == ticket_id
            )
        )

    total = query.count()

    activities = (
        query.order_by(TicketActivity.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "activities": [
            {
                "id": item.id,
                "ticket_id": item.ticket_id,
                "related_ticket_id": item.related_ticket_id,
                "action": item.action,
                "previous_status": item.previous_status,
                "new_status": item.new_status,
                "ticket_snapshot": (
                    json.loads(item.ticket_snapshot)
                    if item.ticket_snapshot
                    else None
                ),
                "details": item.details,
                "actor": item.actor,
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in activities
        ],
    }


# ---------------------------------------------------------
# GET ONE TICKET
# ---------------------------------------------------------

@app.get("/tickets/{ticket_id}", response_model=TicketRecord)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if ticket is None:
        raise ticket_not_found(ticket_id)

    return ticket


# ---------------------------------------------------------
# RESOLVE OR REOPEN
# Reopening creates a new ticket.
# ---------------------------------------------------------

@app.patch("/tickets/{ticket_id}")
@app.patch("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    request: TicketStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if ticket is None:
        raise ticket_not_found(ticket_id)

    previous_status = ticket.status
    new_status = request.status

    if previous_status == new_status:
        return {
            "message": "Ticket status is unchanged",
            "ticket": {
                "id": ticket.id,
                "status": ticket.status,
            },
        }

    try:
        if new_status == "resolved":
            ticket.status = "resolved"

            record_ticket_activity(
                db,
                ticket,
                action="RESOLVED",
                previous_status=previous_status,
                new_status="resolved",
                details="Ticket resolved",
            )

            db.commit()
            db.refresh(ticket)

            return {
                "message": "Ticket resolved successfully",
                "ticket": {
                    "id": ticket.id,
                    "status": ticket.status,
                },
            }

        if (
            previous_status == "resolved"
            and new_status == "open"
        ):
            reopened_ticket = Ticket(
                message=ticket.message,
                category=ticket.category,
                priority=ticket.priority,
                sentiment=ticket.sentiment,
                product_feature=ticket.product_feature,
                suggested_reply=ticket.suggested_reply,
                status="open",
            )

            db.add(reopened_ticket)
            db.flush()

            record_ticket_activity(
                db,
                ticket,
                action="REOPENED",
                previous_status="resolved",
                new_status="open",
                related_ticket_id=reopened_ticket.id,
                details=(
                    f"Reopened as new ticket "
                    f"#{reopened_ticket.id}"
                ),
            )

            record_ticket_activity(
                db,
                reopened_ticket,
                action="CREATED",
                previous_status=None,
                new_status="open",
                related_ticket_id=ticket.id,
                details=(
                    f"Created by reopening ticket "
                    f"#{ticket.id}"
                ),
            )

            db.commit()
            db.refresh(reopened_ticket)

            return {
                "message": "Ticket reopened as a new ticket",
                "ticket": {
                    "id": reopened_ticket.id,
                    "status": reopened_ticket.status,
                },
                "original_ticket_id": ticket.id,
            }

        raise HTTPException(
            status_code=422,
            detail="Unsupported ticket status transition",
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# DELETE TICKET
# ---------------------------------------------------------

@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if ticket is None:
        raise ticket_not_found(ticket_id)

    try:
        record_ticket_activity(
            db,
            ticket,
            action="DELETED",
            previous_status=ticket.status,
            new_status=None,
            details="Ticket permanently deleted",
        )

        db.delete(ticket)
        db.commit()

        return {
            "message": "Ticket deleted; history retained",
            "ticket_id": ticket_id,
        }

    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------

@app.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = db.query(Ticket).count()

    categories = (
        db.query(Ticket.category, func.count(Ticket.id))
        .group_by(Ticket.category)
        .all()
    )

    priorities = (
        db.query(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )

    sentiments = (
        db.query(Ticket.sentiment, func.count(Ticket.id))
        .group_by(Ticket.sentiment)
        .all()
    )

    return AnalyticsResponse(
        total_tickets=total,
        by_category=dict(categories),
        by_priority=dict(priorities),
        by_sentiment=dict(sentiments),
    )


# ---------------------------------------------------------
# BATCH ANALYSIS
# ---------------------------------------------------------

@app.post(
    "/tickets/batch",
    response_model=BatchTicketAnalyzeResponse,
)
def analyze_tickets_batch(
    request: BatchTicketAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    results = []

    try:
        for message in request.messages:
            filter_result = filter_message(message)

            if not filter_result.is_valid:
                results.append(
                    TicketAnalyzeResponse(
                        accepted=False,
                        message=message,
                        status="rejected",
                        reason=filter_result.reason,
                    )
                )
                continue

            analysis = analyze_message(message)

            ticket = Ticket(
                message=message,
                category=analysis["category"],
                priority=analysis["priority"],
                sentiment=analysis["sentiment"],
                product_feature=analysis["product_feature"],
                suggested_reply=analysis["suggested_reply"],
                status="open",
            )

            db.add(ticket)
            db.flush()

            record_ticket_activity(
                db,
                ticket,
                action="CREATED",
                previous_status=None,
                new_status="open",
                details="Ticket created through batch analysis",
            )

            results.append(
                TicketAnalyzeResponse(
                    accepted=True,
                    message=message,
                    status="analyzed",
                    reason=filter_result.reason,
                    category=ticket.category,
                    priority=ticket.priority,
                    sentiment=ticket.sentiment,
                    product_feature=ticket.product_feature,
                    suggested_reply=ticket.suggested_reply,
                    ticket_id=ticket.id,
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    accepted_count = sum(
        result.accepted for result in results
    )

    return BatchTicketAnalyzeResponse(
        total_submitted=len(request.messages),
        accepted_count=accepted_count,
        rejected_count=len(results) - accepted_count,
        results=results,
    )


# ---------------------------------------------------------
# CSV IMPORT
# Requires a CSV column named "message".
# ---------------------------------------------------------

@app.post(
    "/tickets/import/csv",
    response_model=BatchTicketAnalyzeResponse,
)
async def import_tickets_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if (
        not file.filename
        or not file.filename.lower().endswith(".csv")
    ):
        raise HTTPException(
            status_code=400,
            detail="Upload a .csv file",
        )

    raw = await file.read(2_000_001)

    if len(raw) > 2_000_000:
        raise HTTPException(
            status_code=413,
            detail="CSV file must be 2 MB or smaller",
        )

    try:
        decoded = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))

        if not reader.fieldnames:
            raise HTTPException(
                status_code=400,
                detail='CSV must contain a "message" column',
            )

        message_headers = [
            header
            for header in reader.fieldnames
            if header.strip().lower() == "message"
        ]

        if not message_headers:
            raise HTTPException(
                status_code=400,
                detail='CSV must contain a "message" column',
            )

        message_header = message_headers[0]
        messages = [
            (row.get(message_header) or "").strip()
            for row in reader
        ]

    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="CSV must be UTF-8 encoded",
        ) from exc

    if not messages:
        raise HTTPException(
            status_code=400,
            detail="CSV contains no data rows",
        )

    if len(messages) > 100:
        raise HTTPException(
            status_code=400,
            detail="CSV may contain at most 100 messages per import",
        )

    return analyze_tickets_batch(
        BatchTicketAnalyzeRequest(messages=messages),
        db,
        user,
    )


# ---------------------------------------------------------
# JSON IMPORT
# Accepts a JSON array of strings/objects or {"messages": [...]}.
# Each object must contain a "message" field.
# ---------------------------------------------------------

@app.post(
    "/tickets/import/json",
    response_model=BatchTicketAnalyzeResponse,
)
async def import_tickets_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Upload a .json file")

    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="JSON file must be 2 MB or smaller")

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="JSON file must contain valid UTF-8 JSON") from exc

    if isinstance(payload, dict):
        payload = payload.get("messages", payload.get("data"))
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=400,
            detail='JSON must be an array of messages or an object containing a "messages" array',
        )
    if not payload:
        raise HTTPException(status_code=400, detail="JSON contains no messages")
    if len(payload) > 100:
        raise HTTPException(status_code=400, detail="JSON may contain at most 100 messages per import")

    messages = []
    for index, item in enumerate(payload):
        if isinstance(item, str):
            messages.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("message"), str):
            messages.append(item["message"].strip())
        else:
            raise HTTPException(
                status_code=400,
                detail=f'JSON item {index + 1} must be a string or an object with a string "message" field',
            )

    return analyze_tickets_batch(BatchTicketAnalyzeRequest(messages=messages), db, user)


# ---------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------

@app.get("/tickets/export/csv")
def export_tickets_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tickets = (
        db.query(Ticket)
        .order_by(Ticket.id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "message",
        "category",
        "priority",
        "sentiment",
        "product_feature",
        "suggested_reply",
        "status",
        "created_at",
    ])

    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.message,
            ticket.category,
            ticket.priority,
            ticket.sentiment,
            ticket.product_feature,
            ticket.suggested_reply,
            ticket.status,
            (
                ticket.created_at.isoformat()
                if ticket.created_at
                else ""
            ),
        ])

    content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="tickets.csv"'
            )
        },
    )


# ---------------------------------------------------------
# JSON EXPORT
# ---------------------------------------------------------

@app.get("/tickets/export/json")
def export_tickets_json(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tickets = (
        db.query(Ticket)
        .order_by(Ticket.id.asc())
        .all()
    )

    data = [
        {
            "id": ticket.id,
            "message": ticket.message,
            "category": ticket.category,
            "priority": ticket.priority,
            "sentiment": ticket.sentiment,
            "product_feature": ticket.product_feature,
            "suggested_reply": ticket.suggested_reply,
            "status": ticket.status,
            "created_at": (
                ticket.created_at.isoformat()
                if ticket.created_at
                else None
            ),
        }
        for ticket in tickets
    ]

    content = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
    )

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="tickets.json"'
            )
        },
    )
