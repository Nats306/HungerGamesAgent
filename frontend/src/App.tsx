import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { keycloak, logout } from "./auth/keycloak";
import ChatView from "./components/ChatView";
import DocumentsView from "./components/DocumentsView";
import { FlameIcon } from "./components/Landing";
import type { Conversation } from "./types";

type View = "chat" | "documents";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const username = keycloak.tokenParsed?.preferred_username ?? "user";

  const loadConversations = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);
  useEffect(loadConversations, [loadConversations]);

  function newChat() {
    setActiveId(null);
    setChatKey((k) => k + 1);
    setView("chat");
    setMenuOpen(false);
  }

  function open(id: string) {
    setActiveId(id);
    setChatKey((k) => k + 1);
    setView("chat");
    setMenuOpen(false);
  }

  async function removeConversation(id: string) {
    await api.deleteConversation(id).catch(() => undefined);
    if (id === activeId) newChat();
    loadConversations();
  }

  return (
    <div className="layout">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <span className="brand-mark small"><FlameIcon size={18} /></span>
          <span>Hunger Games Agent</span>
        </div>
        <button className="btn primary block" onClick={newChat}>+ New chat</button>
        <nav className="nav">
          <button className={view === "chat" ? "active" : ""} onClick={() => { setView("chat"); setMenuOpen(false); }}>Chat</button>
          <button className={view === "documents" ? "active" : ""} onClick={() => { setView("documents"); setMenuOpen(false); }}>Documents</button>
        </nav>
        <div className="history">
          <div className="history-title">History</div>
          {conversations.length === 0 && <div className="muted small">No conversations yet.</div>}
          {conversations.map((c) => (
            <div key={c.id} className={`history-item ${c.id === activeId && view === "chat" ? "active" : ""}`}>
              <button className="history-open" onClick={() => open(c.id)} title={c.title}>{c.title}</button>
              <button className="history-del" onClick={() => removeConversation(c.id)} aria-label="Delete conversation">×</button>
            </div>
          ))}
        </div>
        <div className="user">
          <div className="avatar">{username.slice(0, 1).toUpperCase()}</div>
          <span className="user-name">{username}</span>
          <button className="btn ghost small" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <button className="menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">☰</button>
          <span>{view === "chat" ? "Chat" : "Documents"}</span>
        </div>
        {view === "chat" ? (
          <ChatView
            key={chatKey}
            conversationId={activeId}
            onConversationStarted={(id) => { setActiveId(id); loadConversations(); }}
          />
        ) : (
          <DocumentsView />
        )}
      </main>
    </div>
  );
}
