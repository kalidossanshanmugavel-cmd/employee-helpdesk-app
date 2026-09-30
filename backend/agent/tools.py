from sqlalchemy.orm import Session

from models import Employee, Ticket, User
from rag.retrieval import search_documents


def search_policy_documents(question: str) -> dict:
    return {"tool": "search_documents", "results": search_documents(question, top_k=3)}


def _employee_for_user(db: Session, current_user: User):
    """
    Resolve the employee record for the authenticated JWT user.

    The demo login accounts use helpdesk.com addresses while the employee
    directory uses company.com addresses, so we keep an explicit mapping
    instead of relying only on matching display names.
    """
    login_to_employee = {
        "admin@helpdesk.com": "EMP001",
        "support@helpdesk.com": "EMP004",
        "hr@helpdesk.com": "EMP003",
        "employee@helpdesk.com": "EMP001",
    }

    employee_code = login_to_employee.get(current_user.email.lower())

    if employee_code:
        employee = (
            db.query(Employee)
            .filter(Employee.employee_code == employee_code)
            .first()
        )

        if employee:
            return employee

    # Fallbacks make the helper work with future accounts whose email/name
    # already matches an employee record.
    employee = (
        db.query(Employee)
        .filter(Employee.email.ilike(current_user.email))
        .first()
    )

    if employee:
        return employee

    return (
        db.query(Employee)
        .filter(Employee.name.ilike(current_user.name))
        .first()
    )


def get_employee_details(db: Session, current_user: User, employee_code: str | None = None) -> dict:
    role = current_user.role.lower()
    if employee_code:
        if role not in {"admin", "hr", "it_support"}:
            return {"tool": "get_employee_details", "found": False, "message": "You can view only your own employee details."}
        employee = db.query(Employee).filter(Employee.employee_code.ilike(employee_code)).first()
    else:
        employee = _employee_for_user(db, current_user)

    if not employee:
        return {"tool": "get_employee_details", "found": False, "message": "Employee record was not found."}

    return {"tool": "get_employee_details", "found": True, "employee": {
        "employee_code": employee.employee_code, "name": employee.name, "email": employee.email,
        "designation": employee.designation, "department": employee.department.name,
        "location": employee.location, "phone": employee.phone,
    }}


def create_it_ticket(db: Session, current_user: User, subject: str, description: str, priority: str = "Medium", employee_code: str | None = None) -> dict:
    role = current_user.role.lower()
    requester = current_user.name

    if employee_code:
        if role not in {"admin", "it_support"}:
            return {"tool": "create_it_ticket", "created": False, "message": "Your role cannot create a ticket for another employee."}
        employee = db.query(Employee).filter(Employee.employee_code.ilike(employee_code)).first()
        if not employee:
            return {"tool": "create_it_ticket", "created": False, "message": f"Employee {employee_code} was not found."}
        requester = employee.name

    next_number = 1000 + db.query(Ticket).count() + 1
    ticket = Ticket(
        ticket_no=f"HD-{next_number}", subject=subject, description=description, category="IT",
        priority=priority, status="Open", requester=requester, assignee="Unassigned",
    )
    db.add(ticket); db.commit(); db.refresh(ticket)
    return {"tool": "create_it_ticket", "created": True, "ticket_no": ticket.ticket_no,
            "subject": ticket.subject, "status": ticket.status, "priority": ticket.priority, "requester": requester}


def view_tickets(
    db: Session,
    current_user: User,
    employee_code: str | None = None,
    status: str | None = None,
) -> dict:
    """
    View tickets with employee/status filtering and backend RBAC.

    Employee:
        - may view only their own tickets
        - explicit another employee code is denied

    IT Support/Admin:
        - may view all tickets
        - may filter by employee code and/or status
    """
    role = current_user.role.lower()
    current_employee = _employee_for_user(db, current_user)

    if role == "employee":
        if not current_employee:
            return {
                "tool": "view_tickets",
                "allowed": False,
                "message": "Employee record was not found.",
                "tickets": [],
            }

        if (
            employee_code
            and employee_code.upper() != current_employee.employee_code.upper()
        ):
            return {
                "tool": "view_tickets",
                "allowed": False,
                "message": "Access denied. You can only view your own tickets.",
                "tickets": [],
            }

        employee_code = current_employee.employee_code

    target_employee = None

    if employee_code:
        target_employee = (
            db.query(Employee)
            .filter(Employee.employee_code.ilike(employee_code))
            .first()
        )

        if not target_employee:
            return {
                "tool": "view_tickets",
                "allowed": False,
                "message": f"Employee {employee_code.upper()} was not found.",
                "tickets": [],
            }

    query = db.query(Ticket)

    if target_employee:
        query = query.filter(
            Ticket.requester == target_employee.name
        )

    if status:
        query = query.filter(
            Ticket.status.ilike(status)
        )

    tickets = (
        query
        .order_by(Ticket.id.desc())
        .all()
    )

    return {
        "tool": "view_tickets",
        "allowed": True,
        "tickets": [
            {
                "ticket_no": ticket.ticket_no,
                "subject": ticket.subject,
                "status": ticket.status,
                "priority": ticket.priority,
                "requester": ticket.requester,
            }
            for ticket in tickets
        ],
    }

def close_ticket(db: Session, current_user: User, ticket_no: str) -> dict:
    if current_user.role.lower() not in {"admin", "it_support"}:
        return {"tool": "close_ticket", "closed": False, "message": "Your role does not have permission to close tickets."}
    ticket = db.query(Ticket).filter(Ticket.ticket_no.ilike(ticket_no)).first()
    if not ticket:
        return {"tool": "close_ticket", "closed": False, "message": "Ticket was not found."}
    ticket.status = "Closed"; db.commit(); db.refresh(ticket)
    return {"tool": "close_ticket", "closed": True, "ticket_no": ticket.ticket_no}


def update_ticket(
    db: Session,
    current_user: User,
    ticket_no: str,
    priority: str | None = None,
) -> dict:
    """
    Update a ticket mentioned in the current chat.

    Admin and IT Support can update ticket priority.
    An Employee may update only their own ticket.
    """
    ticket = (
        db.query(Ticket)
        .filter(Ticket.ticket_no.ilike(ticket_no))
        .first()
    )

    if not ticket:
        return {
            "tool": "update_ticket",
            "updated": False,
            "message": "Ticket was not found.",
        }

    role = current_user.role.lower()

    if role == "employee" and ticket.requester != current_user.name:
        return {
            "tool": "update_ticket",
            "updated": False,
            "message": "You can update only your own tickets.",
        }

    if priority:
        allowed_priorities = {
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "critical": "Critical",
        }

        normalized = allowed_priorities.get(
            priority.lower()
        )

        if not normalized:
            return {
                "tool": "update_ticket",
                "updated": False,
                "message": "Priority must be Low, Medium, High, or Critical.",
            }

        ticket.priority = normalized

    db.commit()
    db.refresh(ticket)

    return {
        "tool": "update_ticket",
        "updated": True,
        "ticket_no": ticket.ticket_no,
        "priority": ticket.priority,
        "status": ticket.status,
    }
