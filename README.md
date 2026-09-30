# Employee Helpdesk - React + FastAPI + PostgreSQL + AI Agent

## Architecture

React -> FastAPI -> JWT HttpOnly Cookie -> Employee Helpdesk Agent -> Tools

Agent tools:
- `search_documents()` - vector RAG over `data/documents/*.txt` using Gemini embeddings when `GEMINI_API_KEY` is configured.
- `get_employee_details()` - reads employee information from PostgreSQL.
- `create_it_ticket()` - creates a real IT ticket in PostgreSQL.

If `GEMINI_API_KEY` is missing, the project remains runnable using deterministic tool routing and keyword document retrieval. Add the key to enable Gemini tool selection, vector embeddings and grounded answer generation.

## 1. PostgreSQL

Create the database:

```sql
CREATE DATABASE employee_helpdesk;
```

Copy `.env.example` to `.env` and update the PostgreSQL password and Gemini key.

## 2. Backend

Run from inside the backend directory. This project intentionally uses non-relative imports.

```powershell
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload
```

FastAPI startup automatically creates tables and seeds departments, users, employees, tickets, knowledge records and announcements.

Swagger: `http://localhost:8000/docs`

## 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Login

Admin:
- Email: `admin@helpdesk.com`
- Password: `Admin@123`

IT Support:
- Email: `support@helpdesk.com`
- Password: `Support@123`

Employee:
- Email: `employee@helpdesk.com`
- Password: `Employee@123`

Authentication uses a JWT stored in an HttpOnly cookie. React does not store the JWT in localStorage or sessionStorage.

## AI Agent test questions

Policy RAG:
- `How many days can I work from home per week?`
- `How many annual leave days do employees get?`
- `When should I submit a travel expense claim?`
- `What should I do if my company laptop is damaged?`

Employee tool:
- `Show my employee details.`

Ticket tool:
- `My laptop is not charging. Create a ticket for me.`
- `Raise an urgent IT ticket because I cannot access my corporate email.`
- `Create a ticket for EMP005 because the laptop is not starting.`
- `Close ticket HD-1001.`

After the agent creates a ticket, open the Tickets page. The new record is stored in PostgreSQL.

## Floating Helpdesk Agent and RBAC

The AI Helpdesk is a bottom-right floating widget available after login. The authenticated user is resolved from the JWT HttpOnly cookie.

- Employee: create tickets, view only own tickets, policy chat, own employee details.
- HR: create tickets, view tickets, policy chat and employee support. Ticket closing is not allowed.
- IT Support: create tickets for self or another employee by Employee ID, view tickets and close tickets.
- Admin: create tickets, view tickets and close tickets.

The backend enforces these permissions. Hiding a frontend button is only a UI convenience and is not the security boundary.


## Human role vs AI Agent

`IT Support` is the human RBAC role. `Helpdesk Agent` is the AI agent. The floating chat uses conversational tools rather than duplicating the normal ticket form.

RBAC summary:
- Employee: create for self, view own tickets, cannot close.
- HR: create for self, view tickets, cannot close.
- IT Support: create for self or another employee using Employee ID, view tickets, close tickets.
- Admin: create for self or another employee using Employee ID, view tickets, close tickets.
