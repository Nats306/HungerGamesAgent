import { login, register } from "../auth/keycloak";

export default function Landing({ error }: { error?: string }) {
  return (
    <div className="landing">
      <div className="landing-card">
        <div className="brand-mark" aria-hidden>
          <FlameIcon />
        </div>
        <h1>Hunger Games Agent</h1>
        <p className="muted">
          Ask anything about Panem, its districts, tributes and Games. Every answer is backed by
          sources from the knowledge base.
        </p>
        {error && <div className="alert error">{error}</div>}
        <div className="landing-actions">
          <button className="btn primary" onClick={login}>Log in</button>
          <button className="btn ghost" onClick={register}>Create account</button>
        </div>
      </div>
    </div>
  );
}

export function FlameIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="currentColor">
      <path d="M16 2c1 5-3 7-3 11 0 2 1 3 2 3-2-3 3-5 3-9 4 3 7 7 7 12a9 9 0 0 1-18 0c0-4 2-6 4-8 0 3 1 4 2 4-1-5 3-8 3-13z" />
    </svg>
  );
}
