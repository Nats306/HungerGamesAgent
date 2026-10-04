import { useState } from "react";
import type { Message } from "../types";

const STATUS_LABEL: Record<string, string> = {
  rejected: "Not enough information",
  clarification: "Needs clarification",
  error: "Error",
};

/** Turns "[1]" citations into small badges. */
function renderAnswer(text: string) {
  return text.split(/(\[\d+\])/g).map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <sup key={i} className="cite">{part.slice(1, -1)}</sup>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

export default function MessageBubble({ message }: { message: Message }) {
  const [open, setOpen] = useState(false);
  const isUser = message.role === "user";
  const label = message.status ? STATUS_LABEL[message.status] : undefined;

  return (
    <div className={`msg ${isUser ? "user" : "assistant"} ${message.status ?? ""}`}>
      {label && <div className="msg-tag">{label}</div>}
      <div className="msg-body">{isUser ? message.content : renderAnswer(message.content)}</div>

      {!isUser && message.sources.length > 0 && (
        <div className="sources">
          <button className="link" onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} sources ({message.sources.length})
          </button>
          {open && (
            <ol>
              {message.sources.map((s) => (
                <li key={s.index}>
                  <div className="source-head">
                    <span className="cite">{s.index}</span>
                    {s.source_url ? (
                      <a href={s.source_url} target="_blank" rel="noreferrer">{s.title}</a>
                    ) : (
                      <strong>{s.title}</strong>
                    )}
                    {s.page && <span className="muted"> · page {s.page}</span>}
                    {s.section && <span className="muted"> · {s.section}</span>}
                    <span className="score" title="Cosine similarity">{(s.similarity * 100).toFixed(0)}%</span>
                  </div>
                  <p className="snippet">{s.snippet}…</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
