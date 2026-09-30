import React, { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { Bot, Building2, FileText, LayoutDashboard, LogOut, Menu, TicketCheck, Users } from "lucide-react";
import api from "./api";

const nav = [
    ["/", "Dashboard", LayoutDashboard],
    ["/employees", "Employees", Users],
    ["/departments", "Departments", Building2],
    ["/tickets", "Tickets", TicketCheck],
    ["/documents", "Knowledge Base", FileText],
];

function App() {
    const [user, setUser] = useState(null);
    const [checkingSession, setCheckingSession] = useState(true);

    useEffect(() => {
        api.get("/auth/me")
            .then((response) => setUser(response.data))
            .catch(() => setUser(null))
            .finally(() => setCheckingSession(false));
    }, []);

    const logout = async () => {
        try {
            await api.post("/auth/logout");
        } finally {
            setUser(null);
        }
    };

    if (checkingSession) return <Loading />;
    if (!user) return <Login onLogin={setUser} />;
    return <Shell user={user} onLogout={logout} />;
}

function Login({ onLogin }) {
    const [email, setEmail] = useState("admin@helpdesk.com");
    const [password, setPassword] = useState("Admin@123");
    const [error, setError] = useState("");

    async function submit(event) {
        event.preventDefault();
        try {
            const { data } = await api.post("/auth/login", { email, password });
            onLogin(data);
        } catch {
            setError("Invalid email or password");
        }
    }

    return (
        <div className="login-page">
            <div className="login-panel brand-panel">
                <div className="logo-mark">EH</div>
                <h1>Employee Helpdesk</h1>
                <p>AI-Powered Employee Helpdesk System for employee support, tickets, policies and smart assistance.</p>
                <div className="feature-row"><TicketCheck /> Track support tickets</div>
                <div className="feature-row"><FileText /> Search company knowledge</div>
                <div className="feature-row"><Bot /> Ask the helpdesk assistant</div>
            </div>
            <form className="login-card" onSubmit={submit}>
                <span className="eyebrow">WELCOME BACK</span>
                <h2>Sign in to Helpdesk</h2>
                <p className="muted">Demo admin credentials are already filled in.</p>
                <label>Email</label>
                <input value={email} onChange={(e) => setEmail(e.target.value)} />
                <label>Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
                {error && <div className="error">{error}</div>}
                <button className="primary" type="submit">Sign In</button>
                <div className="demo-box"><b>Other seeded users</b><br />support@helpdesk.com / Support@123<br />employee@helpdesk.com / Employee@123</div>
            </form>
        </div>
    );
}

function Shell({ user, onLogout }) {
    const [small, setSmall] = useState(false);
    return (
        <div className="app-shell">
            <aside className={small ? "sidebar small" : "sidebar"}>
                <div className="side-head"><div className="logo-mark mini">EH</div>{!small && <b>Helpdesk</b>}<button className="icon-button" onClick={() => setSmall(!small)}><Menu /></button></div>
                <nav>{nav.map(([path, label, Icon]) => <NavLink key={path} to={path} end={path === "/"}><Icon />{!small && <span>{label}</span>}</NavLink>)}</nav>
            </aside>
            <main className="main">
                <header className="topbar"><div><b>Employee Support Portal</b></div><div className="user-box"><div className="avatar">{user.name[0]}</div><div><b>{user.name}</b><small>{user.role === "it_support" ? "IT Support" : user.role}</small></div><button className="icon-button" onClick={onLogout}><LogOut /></button></div></header>
                <div className="content"><Routes><Route path="/" element={<Dashboard />} /><Route path="/employees" element={<Employees />} /><Route path="/departments" element={<Departments />} /><Route path="/tickets" element={<Tickets user={user} />} /><Route path="/documents" element={<Documents />} /><Route path="*" element={<Navigate to="/" />} /></Routes></div>
            </main>
            <ChatWidget user={user} />
        </div>
    );
}

function PageTitle({ title, text }) { return <div className="page-title"><div><h1>{title}</h1><p>{text}</p></div></div>; }
function Badge({ value }) { return <span className={`badge ${value.toLowerCase().replaceAll(" ", "-")}`}>{value}</span>; }

function Dashboard() {
    const [data, setData] = useState(null);
    useEffect(() => { api.get("/dashboard").then((r) => setData(r.data)); }, []);
    if (!data) return <Loading />;
    const cards = [["Employees", data.employees, "purple"], ["Open Tickets", data.openTickets, "orange"], ["In Progress", data.inProgressTickets, "blue"], ["Resolved", data.resolvedTickets, "green"]];
    return <><PageTitle title="Dashboard" text="Live overview from your PostgreSQL helpdesk database." /><div className="stats">{cards.map(([l,v,c]) => <div className={`stat ${c}`} key={l}><span>{l}</span><strong>{v}</strong><small>Current records</small></div>)}</div><div className="grid-2"><section className="card"><h3>Recent Tickets</h3><TicketTable items={data.recentTickets} compact /></section><section className="card"><h3>Announcements</h3>{data.announcements.map(a => <div className={`notice ${a.kind}`} key={a.id}><b>{a.title}</b><p>{a.message}</p></div>)}</section></div></>;
}

function Employees() {
    const [items, setItems] = useState([]);
    useEffect(() => { api.get("/employees").then(r => setItems(r.data)); }, []);
    return <><PageTitle title="Employees" text="Seeded employee directory loaded from PostgreSQL." /><section className="card"><div className="table-wrap"><table><thead><tr><th>Code</th><th>Employee</th><th>Department</th><th>Designation</th><th>Location</th><th>Phone</th></tr></thead><tbody>{items.map(e => <tr key={e.id}><td><b>{e.employee_code}</b></td><td><b>{e.name}</b><small>{e.email}</small></td><td>{e.department}</td><td>{e.designation}</td><td>{e.location}</td><td>{e.phone}</td></tr>)}</tbody></table></div></section></>;
}

function Departments() {
    const [items, setItems] = useState([]);
    useEffect(() => { api.get("/departments").then(r => setItems(r.data)); }, []);
    return <><PageTitle title="Departments" text="Teams and employee counts maintained in PostgreSQL." /><div className="department-grid">{items.map(d => <div className="department-card" key={d.id}><div className="department-icon"><Building2 /></div><h3>{d.name}</h3><p>{d.description}</p><b>{d.employee_count} employees</b></div>)}</div></>;
}

function Tickets({ user }) {
    const [items, setItems] = useState([]);
    const [show, setShow] = useState(false);
    const load = () => api.get("/tickets").then(r => setItems(r.data));
    useEffect(() => {
        load();
    }, []);
    return <><PageTitle title="IT & HR Tickets" text="Create and track support requests stored in PostgreSQL." /><div className="actions"><button className="primary" onClick={() => setShow(!show)}>+ New Ticket</button></div>{show && <TicketForm user={user} done={() => { setShow(false); load(); }} />}<section className="card"><TicketTable items={items} /></section></>;
}

function TicketForm({ user, done }) {
    const [form, setForm] = useState({ subject:"", description:"", category:"Hardware", priority:"Medium", requester:user.name });
    const change = e => setForm({ ...form, [e.target.name]: e.target.value });
    async function submit(e) { e.preventDefault(); await api.post("/tickets", form); done(); }
    return <form className="card form-grid" onSubmit={submit}><div><label>Subject</label><input name="subject" value={form.subject} onChange={change} required /></div><div><label>Category</label><select name="category" value={form.category} onChange={change}><option>Hardware</option><option>Access</option><option>Payroll</option><option>HR</option><option>Software</option></select></div><div><label>Priority</label><select name="priority" value={form.priority} onChange={change}><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select></div><div className="span-2"><label>Description</label><textarea name="description" value={form.description} onChange={change} required /></div><button className="primary" type="submit">Create Ticket</button></form>;
}

function TicketTable({ items, compact=false }) { return <div className="table-wrap"><table><thead><tr><th>Ticket</th><th>Subject</th>{!compact && <th>Category</th>}<th>Priority</th><th>Status</th>{!compact && <th>Assignee</th>}</tr></thead><tbody>{items.map(t => <tr key={t.id}><td><b>{t.ticket_no}</b></td><td>{t.subject}<small>{t.requester}</small></td>{!compact && <td>{t.category}</td>}<td><Badge value={t.priority} /></td><td><Badge value={t.status} /></td>{!compact && <td>{t.assignee}</td>}</tr>)}</tbody></table></div>; }

function Documents() {
    const [items, setItems] = useState([]);
    const [query, setQuery] = useState("");
    useEffect(() => { api.get("/documents").then(r => setItems(r.data)); }, []);
    const filtered = items.filter(x => (x.title+x.category+x.summary).toLowerCase().includes(query.toLowerCase()));
    return <><PageTitle title="Knowledge Base" text="Seeded company policies and employee help articles." /><input className="search" placeholder="Search policies..." value={query} onChange={e => setQuery(e.target.value)} /><div className="document-grid">{filtered.map(d => <article className="document-card" key={d.id}><div className="doc-icon"><FileText /></div><Badge value={d.category} /><h3>{d.title}</h3><p>{d.summary}</p><details><summary>Read policy</summary><p>{d.content}</p></details></article>)}</div></>;
}

function ChatWidget({ user }) {
    const [open, setOpen] = useState(false);
    const [message, setMessage] = useState("");
    const [messages, setMessages] = useState([
        {
            who: "bot",
            text: `Hello ${user.name}! I am your Helpdesk Agent. I will use your ${user.role === "it_support" ? "IT Support" : user.role} permissions.`,
        },
    ]);
    const [busy, setBusy] = useState(false);
    const [actionMode, setActionMode] = useState(null);
    const [lastTicketNo, setLastTicketNo] = useState(null);

    const role = (user.role || "employee").toLowerCase();
    const canClose = ["admin", "it_support"].includes(role);

    const addBotMessage = (text, source = null) => {
        setMessages((current) => [
            ...current,
            {
                who: "bot",
                text: text,
                source: source,
            },
        ]);
    };

    const send = async (event) => {
        event.preventDefault();

        if (!message.trim() || busy) {
            return;
        }

        const typedMessage = message.trim();
        const question = actionMode === "close"
            ? `Close ticket ${typedMessage}`
            : typedMessage;

        setMessages((current) => [
            ...current,
            {
                who: "user",
                text: question,
            },
        ]);

        setMessage("");

        try {
            setBusy(true);

            const response = await api.post(
                "/chat",
                {
                    message: question,
                    preferred_intent: actionMode === "create" ? "create_ticket" : null,
                    last_ticket_no: lastTicketNo,
                }
            );

            addBotMessage(
                response.data.answer,
                response.data.source
            );

            if (response.data.ticket_no) {
                setLastTicketNo(
                    response.data.ticket_no
                );
            }

            setActionMode(null);
        } catch (error) {
            addBotMessage(
                error.response?.data?.detail || "I could not process that request."
            );
        } finally {
            setBusy(false);
        }
    };

    const viewTickets = async () => {
        try {
            setBusy(true);

            const response = await api.get(
                "/tickets"
            );

            if (response.data.length === 0) {
                addBotMessage(
                    "No tickets are available for your account."
                );
                return;
            }

            const summary = response.data
                .slice(0, 8)
                .map((ticket) => {
                    return `${ticket.ticket_no} - ${ticket.subject} - ${ticket.status}`;
                })
                .join("\n");

            addBotMessage(
                `Tickets visible to ${user.role === "it_support" ? "IT Support" : user.role}:\n${summary}`
            );
        } catch (error) {
            addBotMessage(
                error.response?.data?.detail || "Unable to load tickets."
            );
        } finally {
            setBusy(false);
        }
    };


    return (
        <>
            {!open && (
                <button
                    className="chat-launcher"
                    onClick={() => setOpen(true)}
                    title="Open Helpdesk Agent"
                >
                    <Bot />
                    <span>Helpdesk</span>
                </button>
            )}

            {open && (
                <section className="floating-chat">
                    <div className="floating-chat-head">
                        <div className="bot-avatar">
                            <Bot />
                        </div>

                        <div className="floating-chat-title">
                            <b>Helpdesk Agent</b>
                            <small>{user.name} • {user.role === "it_support" ? "IT Support" : user.role}</small>
                        </div>

                        <button
                            className="chat-close"
                            onClick={() => setOpen(false)}
                            title="Close chat"
                        >
                            ×
                        </button>
                    </div>

                    <div className="chat-actions">
                        <button
                            onClick={() => {
                                setActionMode("create");
                                addBotMessage(
                                    canClose
                                        ? "Describe the issue. To create it for another employee, include the Employee ID, for example: EMP005 laptop is not starting, high priority."
                                        : "Describe your issue and I will create the ticket for your account."
                                );
                            }}
                        >
                            Create Ticket
                        </button>

                        <button onClick={viewTickets}>
                            View Tickets
                        </button>

                        {canClose && (
                            <button
                                onClick={() => {
                                    setActionMode("close");
                                    addBotMessage("Enter the ticket number you want to close, for example HD-1001.");
                                }}
                            >
                                Close Ticket
                            </button>
                        )}
                    </div>

                    {actionMode && (
                        <div className="chat-mode-hint">
                            {actionMode === "create" ? "Creating ticket conversationally" : "Closing ticket conversationally"}
                        </div>
                    )}

                    <div className="floating-messages">
                        {messages.map((currentMessage, index) => {
                            return (
                                <div
                                    key={index}
                                    className={`message ${currentMessage.who}`}
                                >
                                    <p>{currentMessage.text}</p>

                                    {currentMessage.source && (
                                        <small>
                                            Source: {currentMessage.source}
                                        </small>
                                    )}
                                </div>
                            );
                        })}

                        {busy && (
                            <div className="message bot">
                                <p>Working...</p>
                            </div>
                        )}
                    </div>

                    <form
                        className="chat-input"
                        onSubmit={send}
                    >
                        <input
                            placeholder="Ask about policies or support..."
                            value={message}
                            onChange={(event) => {
                                setMessage(event.target.value);
                            }}
                        />

                        <button
                            className="primary"
                            type="submit"
                            disabled={busy}
                        >
                            Send
                        </button>
                    </form>
                </section>
            )}
        </>
    );
}


function Loading() { return <div className="loading">Loading data from FastAPI...</div>; }

export default App;
