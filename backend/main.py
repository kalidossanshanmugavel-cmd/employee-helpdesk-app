from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

load_dotenv()

from agent.agent import run_helpdesk_agent
from auth import clear_auth_cookie, create_access_token, get_current_user, set_auth_cookie, user_response, verify_password
from database import Base, SessionLocal, engine, get_db
from models import Announcement, Department, Document, Employee, Ticket, User
from schemas import ChatRequest, LoginRequest, TicketCreate, TicketUpdate
from seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
        print("PostgreSQL tables ready and seed data verified.")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Employee Helpdesk API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Employee Helpdesk API is running",
        "database": "PostgreSQL",
        "agent": "Employee Helpdesk Agent",
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return user_response(user)


@app.get("/api/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return user_response(current_user)


@app.post("/api/auth/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out successfully"}


def serialize_tickets(items):
    return [
        {
            "id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "subject": ticket.subject,
            "description": ticket.description,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "requester": ticket.requester,
            "assignee": ticket.assignee,
            "created_at": ticket.created_at.isoformat(),
        }
        for ticket in items
    ]


@app.get("/api/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status_counts = dict(
        db.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )

    return {
        "employees": db.query(Employee).count(),
        "departments": db.query(Department).count(),
        "tickets": db.query(Ticket).count(),
        "documents": db.query(Document).count(),
        "openTickets": status_counts.get("Open", 0),
        "inProgressTickets": status_counts.get("In Progress", 0),
        "resolvedTickets": status_counts.get("Resolved", 0) + status_counts.get("Closed", 0),
        "recentTickets": serialize_tickets(
            db.query(Ticket).order_by(Ticket.id.desc()).limit(5).all()
        ),
        "announcements": [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "kind": item.kind,
            }
            for item in db.query(Announcement).all()
        ],
    }


@app.get("/api/departments")
def departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        {
            "id": department.id,
            "name": department.name,
            "description": department.description,
            "employee_count": db.query(Employee)
            .filter(Employee.department_id == department.id)
            .count(),
        }
        for department in db.query(Department).order_by(Department.name).all()
    ]


@app.get("/api/employees")
def employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "name": employee.name,
            "email": employee.email,
            "designation": employee.designation,
            "location": employee.location,
            "phone": employee.phone,
            "department": employee.department.name,
        }
        for employee in db.query(Employee).order_by(Employee.id).all()
    ]


@app.get("/api/tickets")
def tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Ticket)

    if current_user.role.lower() == "employee":
        query = query.filter(Ticket.requester == current_user.name)

    return serialize_tickets(
        query.order_by(Ticket.id.desc()).all()
    )


@app.post("/api/tickets")
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    next_number = 1000 + db.query(Ticket).count() + 1

    ticket = Ticket(
        ticket_no=f"HD-{next_number}",
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="Open",
        requester=current_user.name,
        assignee="Unassigned",
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return serialize_tickets([ticket])[0]


@app.patch("/api/tickets/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role.lower() not in {"admin", "it_support", "hr"}:
        raise HTTPException(status_code=403, detail="You do not have permission to update tickets")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(ticket, field, value)

    db.commit()
    db.refresh(ticket)
    return serialize_tickets([ticket])[0]


@app.post("/api/tickets/{ticket_no}/close")
def close_ticket(
    ticket_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() not in {"admin", "it_support"}:
        raise HTTPException(
            status_code=403,
            detail="Only Admin and IT Support roles can close tickets",
        )

    ticket = (
        db.query(Ticket)
        .filter(func.lower(Ticket.ticket_no) == ticket_no.lower())
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = "Closed"
    db.commit()
    db.refresh(ticket)

    return serialize_tickets([ticket])[0]


@app.get("/api/permissions")
def permissions(current_user: User = Depends(get_current_user)):
    role = current_user.role.lower()

    return {
        "role": role,
        "create_ticket": True,
        "view_ticket": True,
        "close_ticket": role in {"admin", "it_support"},
        "ticket_scope": "own" if role == "employee" else "all",
    }


@app.get("/api/documents")
def documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        {
            "id": document.id,
            "title": document.title,
            "category": document.category,
            "summary": document.summary,
            "content": document.content,
            "updated_at": document.updated_at.isoformat(),
        }
        for document in db.query(Document).order_by(Document.title).all()
    ]


@app.post("/api/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return run_helpdesk_agent(
        message=payload.message,
        preferred_intent=payload.preferred_intent,
        last_ticket_no=payload.last_ticket_no,
        db=db,
        current_user=current_user,
    )
