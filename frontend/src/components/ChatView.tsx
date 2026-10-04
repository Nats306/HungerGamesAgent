import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Message } from "../types";
import MessageBubble from "./MessageBubble";

const SUGGESTIONS = [
  "Who won the 74th Hunger Games?",
  "What is a Quarter Quell?",
  "Who is Lucy Gray Baird?",
  "What happens in District 13?",
];

interface Props {
  conversationId: string | null;
  onConversationStarted: (id: string) => void;
}

export default function ChatView({ conversationId, onConversationStarted }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const justCreated = useRef<string | null>(null);

  // Load the history when a conversation is selected.
  useEffect(() => {
    setLoadError(null);
    if (!conversationId) {
      setMessages([]);
      return;
    }
    if (justCreated.current === conversationId) return; // we already have its messages
    api
      .conversation(conversationId)
      .then((c) => setMessages(c.messages))
      .catch((e) => setLoadError(e.message));
  }, [conversationId]);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages, sending]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || sending) return;
    setInput("");
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: question, sources: [] }]);
    setSending(true);
    try {
      const res = await api.ask(question, conversationId);
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: "assistant", content: res.answer, status: res.status, sources: res.sources },
      ]);
      if (!conversationId) {
        justCreated.current = res.conversation_id;
        onConversationStarted(res.conversation_id);
      }
    } catch (e) {
      setMessages((m) => [
        ...m,
        { id: `e-${Date.now()}`, role: "assistant", content: (e as Error).message, status: "error", sources: [] },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="chat">
      <div className="messages">
        {loadError && <div className="alert error">{loadError}</div>}
        {messages.length === 0 && !loadError && (
          <div className="empty">
            <h2>What do you want to know about Panem?</h2>
            <p className="muted">Answers come only from the knowledge base, with their sources.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
        {sending && (
          <div className="msg assistant thinking">
            <span className="dot" /><span className="dot" /><span className="dot" />
            <span className="muted">Searching the knowledge base…</span>
          </div>
        )}
        <div ref={bottom} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="Ask a question about The Hunger Games…"
          rows={1}
          maxLength={2000}
          disabled={sending}
        />
        <button className="btn primary" disabled={sending || !input.trim()}>Send</button>
      </form>
    </section>
  );
}
