from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TicketCreate(BaseModel):
    subject: str
    description: str
    category: str
    priority: str = "Medium"
    requester: str


class TicketUpdate(BaseModel):
    status: str | None = None
    assignee: str | None = None
    priority: str | None = None


class ChatRequest(BaseModel):
    message: str
    preferred_intent: str | None = None
    last_ticket_no: str | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
