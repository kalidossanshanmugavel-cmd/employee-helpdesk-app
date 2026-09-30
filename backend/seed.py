from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import Announcement, Department, Document, Employee, Ticket, User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_database(db: Session):
    if db.query(Department).count() == 0:
        db.add_all([
            Department(name="Engineering", description="Product engineering and platform development"),
            Department(name="Human Resources", description="People operations, hiring and employee support"),
            Department(name="Information Technology", description="Devices, access, network and technical support"),
            Department(name="Finance", description="Payroll, expenses and financial operations"),
            Department(name="Sales", description="Customer acquisition and account growth"),
        ])
        db.commit()

    departments = {item.name: item.id for item in db.query(Department).all()}

    if db.query(User).count() == 0:
        db.add_all([
            User(name="Admin User", email="admin@helpdesk.com", password_hash=pwd.hash("Admin@123"), role="admin"),
            User(name="Priya HR", email="hr@helpdesk.com", password_hash=pwd.hash("Hr@123"), role="hr"),
            User(name="Karthik IT", email="support@helpdesk.com", password_hash=pwd.hash("Support@123"), role="it_support"),
            User(name="Arun Kumar", email="employee@helpdesk.com", password_hash=pwd.hash("Employee@123"), role="employee"),
        ])
        db.commit()

    # Upgrade older demo databases from the former human "agent" role.
    legacy_support = db.query(User).filter(User.role == "agent").first()
    if legacy_support:
        legacy_support.role = "it_support"
        legacy_support.email = "support@helpdesk.com"
        legacy_support.password_hash = pwd.hash("Support@123")
        db.commit()

    if db.query(Employee).count() == 0:
        rows = [
            ("EMP001", "Arun Kumar", "arun@company.com", "Senior Developer", "Chennai", "9876500001", "Engineering"),
            ("EMP002", "Bala Murugan", "bala@company.com", "QA Engineer", "Chennai", "9876500002", "Engineering"),
            ("EMP003", "Cathy Joseph", "cathy@company.com", "HR Executive", "Bengaluru", "9876500003", "Human Resources"),
            ("EMP004", "David Raj", "david@company.com", "IT Support Engineer", "Chennai", "9876500004", "Information Technology"),
            ("EMP005", "Elan Kumar", "elan@company.com", "Finance Analyst", "Hyderabad", "9876500005", "Finance"),
            ("EMP006", "Farah Khan", "farah@company.com", "Sales Manager", "Bengaluru", "9876500006", "Sales"),
            ("EMP007", "Gokul S", "gokul@company.com", "React Developer", "Chennai", "9876500007", "Engineering"),
            ("EMP008", "Harini P", "harini@company.com", "Recruiter", "Coimbatore", "9876500008", "Human Resources"),
        ]
        db.add_all([Employee(employee_code=c,name=n,email=e,designation=d,location=l,phone=p,department_id=departments[dept]) for c,n,e,d,l,p,dept in rows])
        db.commit()

    if db.query(Ticket).count() == 0:
        db.add_all([
            Ticket(ticket_no="HD-1001", subject="Laptop battery drains quickly", description="Battery lasts less than one hour.", category="Hardware", priority="High", status="Open", requester="Arun Kumar", assignee="Karthik IT"),
            Ticket(ticket_no="HD-1002", subject="VPN access required", description="Need VPN access for remote development.", category="Access", priority="Medium", status="In Progress", requester="Bala Murugan", assignee="Karthik IT"),
            Ticket(ticket_no="HD-1003", subject="Payroll clarification", description="Need clarification about reimbursement entry.", category="Payroll", priority="Low", status="Resolved", requester="Elan Kumar", assignee="Priya HR"),
            Ticket(ticket_no="HD-1004", subject="Email password reset", description="Unable to sign in to corporate email.", category="Access", priority="Critical", status="Open", requester="Harini P", assignee="Karthik IT"),
            Ticket(ticket_no="HD-1005", subject="Monitor replacement", description="External monitor has display flickering.", category="Hardware", priority="Medium", status="Closed", requester="Gokul S", assignee="Karthik IT"),
            Ticket(ticket_no="HD-1006", subject="Leave balance mismatch", description="Portal leave balance needs verification.", category="HR", priority="Medium", status="In Progress", requester="Cathy Joseph", assignee="Priya HR"),
        ])
        db.commit()

    if db.query(Document).count() == 0:
        db.add_all([
            Document(title="Leave Policy", category="HR Policy", summary="Annual, sick and casual leave guidance.", content="Employees receive annual leave based on company policy. Apply through the HR portal and obtain manager approval."),
            Document(title="Work From Home Policy", category="HR Policy", summary="Hybrid work eligibility and expectations.", content="Eligible employees may use approved work-from-home days after manager confirmation and must remain available during core hours."),
            Document(title="Travel & Expense Policy", category="Finance", summary="Business travel booking and reimbursement rules.", content="Use approved booking channels. Submit itemized receipts and expense claims within the required reimbursement period."),
            Document(title="Laptop & Device Policy", category="IT Policy", summary="Company device usage, security and replacement.", content="Company devices are for authorized business use. Report loss, damage or security incidents to IT immediately."),
            Document(title="Health Insurance Guide", category="Benefits", summary="Employee health insurance and claims overview.", content="Eligible employees can access health insurance benefits. Contact HR for enrollment, dependent and claims assistance."),
        ])
        db.commit()

    if db.query(Announcement).count() == 0:
        db.add_all([
            Announcement(title="Security Reminder", message="Complete the quarterly security awareness module before Friday.", kind="warning"),
            Announcement(title="Helpdesk Upgrade", message="The new employee helpdesk now provides faster ticket tracking and policy search.", kind="info"),
            Announcement(title="Benefits Window", message="Benefits information has been updated in the Knowledge Base.", kind="success"),
        ])
        db.commit()
