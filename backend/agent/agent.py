import re
import json
import os

from google import genai
from sqlalchemy.orm import Session

from models import User
from agent.tools import close_ticket, create_it_ticket, get_employee_details, search_policy_documents, update_ticket, view_tickets

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """
You are an Employee Helpdesk Agent.
Choose exactly one tool for the user's actual request. A UI button may provide a preferred intent, but it is only a hint. Always classify the user's latest message independently. For example, if preferred intent is create_ticket but the user asks 'What is the WFH policy?', choose search_documents and DO NOT create a ticket.

Possible intents/tools:
1. greeting - only for a simple greeting such as hi, hello, hey. Do not list capabilities unless asked.
2. capabilities - when the user asks what you can do or how you can help.
3. search_documents - company leave, WFH, travel, insurance, laptop and policy questions.
4. get_employee_details - employee profile/details questions.
5. create_it_ticket - when the user clearly asks to create/log/raise an IT support ticket. Admin and IT Support may create for another employee when an employee code such as EMP005 is supplied.
6. view_tickets - when the user asks to view/list/show tickets.
7. close_ticket - when the user asks to close a ticket. RBAC is enforced by the tool.
8. update_ticket - when the user changes the priority of a ticket, including conversational follow-ups such as "high priority", "make it critical", or "change it to low priority".
9. out_of_scope - weather/climate, sports, coding, general knowledge, entertainment, or anything unrelated to company documents, employee information, or helpdesk tickets.

Return JSON only using this structure:
{
  "tool": "greeting|capabilities|search_documents|get_employee_details|create_it_ticket|view_tickets|close_ticket|close_tickets|update_ticket|ticket_information|out_of_scope",
  "employee_code": null,
  "ticket_no": null,
  "subject": null,
  "description": null,
  "priority": "Medium"
}
Do not create a ticket unless the user asks to create, raise, log or submit one.
"""


def _fallback_decision(message: str, preferred_intent: str | None = None, last_ticket_no: str | None = None) -> dict:
    text = message.strip().lower()

    # Mentioning "ticket" is not sufficient for a database write.
    ticket_information_questions = [
        "is it ticket",
        "is this ticket",
        "is that ticket",
        "what is a ticket",
        "what is ticket",
        "can i create a ticket",
        "can i raise a ticket",
        "do i have a ticket",
        "do i have any ticket",
    ]

    if any(item in text for item in ticket_information_questions):
        return {
            "tool": "ticket_information",
        }

    text = message.lower().strip()

    # Simple conversation is handled without RAG.
    greetings = {"hi", "hello", "hey", "hi there", "hello there", "good morning", "good afternoon", "good evening"}
    if text.rstrip("!.") in greetings:
        return {"tool": "greeting"}

    capability_phrases = [
        "how can you help", "how can you help me", "what can you do",
        "what do you do", "what can you help with", "helpdesk capabilities",
    ]
    if any(phrase in text for phrase in capability_phrases):
        return {"tool": "capabilities"}

    # Conversational follow-up to the most recently created/viewed ticket.
    # Example: "high priority" after creating HD-1011.
    if last_ticket_no:
        priority_followups = {
            "high priority": "High",
            "make it high": "High",
            "make it high priority": "High",
            "medium priority": "Medium",
            "make it medium": "Medium",
            "low priority": "Low",
            "make it low": "Low",
            "critical": "Critical",
            "critical priority": "Critical",
            "make it critical": "Critical",
        }

        normalized_text = text.rstrip("!.")

        if normalized_text in priority_followups:
            return {
                "tool": "update_ticket",
                "ticket_no": last_ticket_no,
                "priority": priority_followups[normalized_text],
            }

        if normalized_text in {"close it", "close this ticket", "close that ticket"}:
            return {
                "tool": "close_ticket",
                "ticket_no": last_ticket_no,
            }

    # Clearly unrelated requests must not be sent to document RAG.
    out_of_scope_terms = [
        "weather", "climate", "temperature outside", "rain today", "forecast",
        "cricket", "football score", "movie", "recipe", "write python",
        "python code", "stock price", "news today",
    ]
    if any(term in text for term in out_of_scope_terms):
        return {"tool": "out_of_scope"}

    # Questions about the authenticated user's own employee record.
    # These must be handled by PostgreSQL employee lookup, not by document RAG.
    my_employee_phrases = [
        "my employee details",
        "show my employee details",
        "my employee id",
        "what is my employee id",
        "what's my employee id",
        "which department am i in",
        "what department am i in",
        "my department",
        "what is my designation",
        "what's my designation",
        "my designation",
        "where am i located",
        "my location",
        "show my profile",
        "my profile",
        "my details",
    ]

    if any(phrase in text for phrase in my_employee_phrases):
        return {
            "tool": "get_employee_details",
            "employee_code": None,
        }

    # Policy/RAG questions always override a previously clicked Create Ticket button.
    policy_terms = [
        "policy", "work from home", "wfh", "leave", "insurance",
        "travel reimbursement", "travel policy", "laptop policy",
        "benefit", "how many days", "what is", "explain",
    ]
    if any(term in text for term in policy_terms) and (
        "?" in text or text.startswith(("what", "how", "explain", "tell me"))
    ):
        return {"tool": "search_documents"}

    if "close ticket" in text:
        import re

        match = re.search(r"HD-\d+", message, re.IGNORECASE)
        return {
            "tool": "close_ticket",
            "ticket_no": match.group(0).upper() if match else None,
        }

    if any(word in text for word in ["view ticket", "show ticket", "list ticket", "my tickets"]):
        return {"tool": "view_tickets"}

    if any(word in text for word in ["create ticket", "raise ticket", "log ticket", "submit ticket"]):
        import re
        employee_match = re.search(r"EMP\d+", message, re.IGNORECASE)
        return {
            "tool": "create_it_ticket",
            "employee_code": employee_match.group(0).upper() if employee_match else None,
            "subject": message[:120],
            "description": message,
            "priority": "High" if "urgent" in text or "critical" in text else "Medium",
        }

    if any(word in text for word in ["my details", "employee details", "my profile", "employee profile"]):
        return {"tool": "get_employee_details", "employee_code": None}

    # The Create Ticket button is a hint only. If the message looks like an
    # actual problem statement, use it to create the ticket. Questions above
    # have already been routed to RAG.
    if preferred_intent == "create_ticket":
        import re
        employee_match = re.search(r"EMP\d+", message, re.IGNORECASE)
        return {
            "tool": "create_it_ticket",
            "employee_code": employee_match.group(0).upper() if employee_match else None,
            "subject": message[:120],
            "description": message,
            "priority": "High" if "urgent" in text or "critical" in text or "high priority" in text else "Medium",
        }

    return {"tool": "search_documents"}


def _choose_tool(message: str, preferred_intent: str | None = None, last_ticket_no: str | None = None) -> dict:
    normalized_message = message.strip().lower()

    # Parse ticket-list queries before Gemini so Employee ID/status filters
    # cannot be ignored by the model.
    if (
        "ticket" in normalized_message
        and any(
            word in normalized_message
            for word in ["show", "view", "list"]
        )
    ):
        employee_match = re.search(
            r"EMP\d+",
            message,
            re.IGNORECASE,
        )

        ticket_status = None

        if "open" in normalized_message:
            ticket_status = "Open"
        elif "in progress" in normalized_message:
            ticket_status = "In Progress"
        elif "closed" in normalized_message:
            ticket_status = "Closed"
        elif "resolved" in normalized_message:
            ticket_status = "Resolved"

        return {
            "tool": "view_tickets",
            "employee_code": (
                employee_match.group(0).upper()
                if employee_match
                else None
            ),
            "status": ticket_status,
        }

    normalized_message = message.strip().lower().rstrip("?!.")
    # Support one or many ticket numbers in close commands.
    # Examples:
    # "close 1013"
    # "1013, 1014, 1015 - close it"
    # "close HD-1013 and HD-1014"
    close_words = ["close", "close it", "close ticket", "close tickets"]

    if any(word in normalized_message for word in close_words):
        raw_numbers = re.findall(
            r"(?:HD-)?(\d{4,})",
            message,
            re.IGNORECASE,
        )

        if raw_numbers:
            ticket_numbers = [
                f"HD-{number}"
                for number in raw_numbers
            ]

            return {
                "tool": "close_tickets",
                "ticket_numbers": ticket_numbers,
            }

    ticket_information_questions = {
        "is it ticket",
        "is this ticket",
        "is that ticket",
        "what is a ticket",
        "what is ticket",
        "can i create a ticket",
        "can i raise a ticket",
        "do i have a ticket",
        "do i have any ticket",
    }

    # Apply this BEFORE Gemini/RAG routing so informational ticket questions
    # can never fall through to document search or ticket creation.
    if normalized_message in ticket_information_questions:
        return {
            "tool": "ticket_information",
        }

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return _fallback_decision(message, preferred_intent, last_ticket_no)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=(
            f"{SYSTEM_PROMPT}\n\n"
            f"Preferred UI intent (hint only): {preferred_intent or 'none'}\n"
            f"Most recent ticket in this conversation: {last_ticket_no or 'none'}\n"
            f"User request: {message}"
        ),
        config={"response_mime_type": "application/json"},
    )

    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        return _fallback_decision(message, preferred_intent, last_ticket_no)


def _answer_from_documents(message: str, tool_result: dict) -> dict:
    results = tool_result.get("results", [])

    if not results:
        return {
            "answer": "I could not find that information in the helpdesk policy documents.",
            "source": "Policy documents",
            "tool": "search_documents",
        }

    api_key = os.getenv("GEMINI_API_KEY")
    context = "\n\n".join(
        f"SOURCE: {item['source']}\n{item['content']}"
        for item in results
    )

    if not api_key:
        first = results[0]
        return {
            "answer": first["content"],
            "source": first["source"],
            "tool": "search_documents",
        }

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=(
            "Answer the employee question only from the supplied context. "
            "If the answer is absent, say it is not available in the documents.\n\n"
            f"Question: {message}\n\nContext:\n{context}"
        ),
    )

    return {
        "answer": response.text,
        "source": ", ".join(item["source"] for item in results),
        "tool": "search_documents",
    }


def run_helpdesk_agent(message: str, db: Session, current_user: User, preferred_intent: str | None = None, last_ticket_no: str | None = None) -> dict:
    decision = _choose_tool(message, preferred_intent, last_ticket_no)
    tool_name = decision.get("tool", "out_of_scope")

    if tool_name == "greeting":
        return {
            "answer": f"Hi {current_user.name}!",
            "source": None,
            "tool": "greeting",
        }

    if tool_name == "capabilities":
        return {
            "answer": (
                "I can help with company policies and documents, employee information, "
                "creating and viewing helpdesk tickets, and closing tickets when your role permits it."
            ),
            "source": None,
            "tool": "capabilities",
        }

    if tool_name == "ticket_information":
        normalized_message = message.strip().lower()

        if normalized_message.rstrip("?!.") in {
            "is it ticket",
            "is this ticket",
            "is that ticket",
        }:
            return {
                "answer": "No. That was a company policy answer. No ticket was created.",
                "source": None,
                "tool": "ticket_information",
            }

        return {
            "answer": (
                "A helpdesk ticket is a support request. "
                "I create one only when you clearly ask me to create, raise, open, or log a ticket for an actual issue."
            ),
            "source": None,
            "tool": "ticket_information",
        }

    if tool_name == "out_of_scope":
        return {
            "answer": (
                "Sorry, I can only help with company documents, employee information, "
                "and helpdesk tickets."
            ),
            "source": None,
            "tool": "out_of_scope",
        }

    if tool_name == "get_employee_details":
        result = get_employee_details(db, current_user, decision.get("employee_code"))
        if not result.get("found"):
            return {"answer": result["message"], "source": None, "tool": tool_name}

        employee = result["employee"]
        normalized_message = message.lower().strip()

        if "employee id" in normalized_message or "employee code" in normalized_message:
            answer = (
                f"Your employee ID is {employee['employee_code']}."
            )

        elif "department" in normalized_message:
            answer = (
                f"You are in the {employee['department']} department."
            )

        elif "designation" in normalized_message or "job title" in normalized_message:
            answer = (
                f"Your designation is {employee['designation']}."
            )

        elif "where am i located" in normalized_message or "my location" in normalized_message:
            answer = (
                f"Your location is {employee['location']}."
            )

        elif "email" in normalized_message:
            answer = (
                f"Your employee email is {employee['email']}."
            )

        else:
            answer = (
                f"Employee: {employee['name']} ({employee['employee_code']}). "
                f"Designation: {employee['designation']}. "
                f"Department: {employee['department']}. "
                f"Location: {employee['location']}. "
                f"Email: {employee['email']}."
            )

        return {
            "answer": answer,
            "source": None,
            "tool": tool_name,
        }

    if tool_name == "view_tickets":
        result = view_tickets(
            db=db,
            current_user=current_user,
            employee_code=decision.get("employee_code"),
            status=decision.get("status"),
        )

        if not result.get("allowed", True):
            return {
                "answer": result["message"],
                "source": None,
                "tool": tool_name,
            }

        tickets = result.get("tickets", [])

        if not tickets:
            return {
                "answer": "No matching tickets were found.",
                "source": None,
                "tool": tool_name,
            }

        lines = [
            f"{item['ticket_no']} - {item['subject']} - {item['status']}"
            for item in tickets
        ]

        return {
            "answer": "\n".join(lines),
            "source": None,
            "tool": tool_name,
        }

    if tool_name == "close_tickets":
        ticket_numbers = decision.get("ticket_numbers") or []

        if not ticket_numbers:
            return {
                "answer": "Please provide the ticket number or ticket numbers to close.",
                "source": None,
                "tool": tool_name,
            }

        closed = []
        failed = []

        for ticket_no in ticket_numbers:
            result = close_ticket(
                db,
                current_user,
                ticket_no,
            )

            if result.get("closed"):
                closed.append(ticket_no)
            else:
                failed.append(
                    f"{ticket_no}: {result.get('message', 'Could not close ticket.')}"
                )

        parts = []

        if closed:
            parts.append(
                "Closed successfully: "
                + ", ".join(closed)
                + "."
            )

        if failed:
            parts.append(
                "Not closed: "
                + " ".join(failed)
            )

        return {
            "answer": " ".join(parts),
            "source": None,
            "tool": tool_name,
            "ticket_no": closed[-1] if closed else None,
        }

    if tool_name == "close_ticket":
        ticket_no = decision.get("ticket_no")

        if not ticket_no:
            return {
                "answer": "Please provide the ticket number, for example HD-1001.",
                "source": None,
                "tool": tool_name,
            }

        result = close_ticket(db, current_user, ticket_no)

        if not result.get("closed"):
            return {
                "answer": result["message"],
                "source": None,
                "tool": tool_name,
            }

        return {
            "answer": f"Ticket {result['ticket_no']} was closed successfully.",
            "source": None,
            "tool": tool_name,
            "ticket_no": result["ticket_no"],
        }

    if tool_name == "update_ticket":
        ticket_no = decision.get("ticket_no") or last_ticket_no

        if not ticket_no:
            return {
                "answer": "Please tell me which ticket you want to update.",
                "source": None,
                "tool": tool_name,
            }

        result = update_ticket(
            db=db,
            current_user=current_user,
            ticket_no=ticket_no,
            priority=decision.get("priority"),
        )

        if not result.get("updated"):
            return {
                "answer": result["message"],
                "source": None,
                "tool": tool_name,
                "ticket_no": ticket_no,
            }

        return {
            "answer": (
                f"Ticket {result['ticket_no']} priority has been updated "
                f"to {result['priority']}."
            ),
            "source": None,
            "tool": tool_name,
            "ticket_no": result["ticket_no"],
        }

    if tool_name == "create_it_ticket":
        normalized_message = message.strip().lower()
        explicit_create_verbs = ["create", "raise", "open", "log", "submit"]

        if (
            normalized_message.endswith("?")
            and not any(
                verb in normalized_message
                for verb in explicit_create_verbs
            )
        ):
            return {
                "answer": "No ticket was created. Please clearly ask me to create a ticket and describe the support issue.",
                "source": None,
                "tool": "ticket_information",
            }
        result = create_it_ticket(
            db=db,
            current_user=current_user,
            subject=decision.get("subject") or "IT support request",
            description=decision.get("description") or message,
            priority=decision.get("priority") or "Medium",
            employee_code=decision.get("employee_code"),
        )
        if not result.get("created"):
            return {"answer": result["message"], "source": None, "tool": tool_name}
        # Use natural wording for self-service tickets.
        # Keep the employee identity when IT Support/Admin creates
        # a ticket on behalf of another employee.
        target_employee_code = decision.get("employee_code")

        if target_employee_code:
            answer = (
                f"Ticket {result['ticket_no']} was created successfully "
                f"for {result['requester']} ({target_employee_code}) "
                f"with {result['priority']} priority."
            )
        else:
            answer = (
                f"Ticket {result['ticket_no']} was created successfully "
                f"for you with {result['priority']} priority."
            )

        return {
            "answer": answer,
            "source": None,
            "tool": tool_name,
            "ticket_no": result["ticket_no"],
        }

    result = search_policy_documents(message)
    return _answer_from_documents(message, result)
