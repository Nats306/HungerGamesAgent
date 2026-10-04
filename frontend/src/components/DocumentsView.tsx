import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { DocumentItem } from "../types";

const ACCEPT = ".pdf,.txt,.md,.markdown,.csv,.docx";

export default function DocumentsView() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [filter, setFilter] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api.documents().then(setDocs).catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  // While something is processing, refresh every 3 s so the user sees when it's ready.
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing")) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.documents();
        fresh.forEach((d) => {
          const before = docs.find((o) => o.id === d.id);
          if (before?.status === "processing" && d.status === "ready")
            setNotice(`"${d.title}" was processed: ${d.chunk_count} fragments added to the knowledge base.`);
          if (before?.status === "processing" && d.status === "failed")
            setError(`"${d.title}" could not be processed: ${d.error}`);
        });
        setDocs(fresh);
      } catch {
        /* keep polling */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [docs]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    setNotice(null);
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        const doc = await api.upload(file);
        setDocs((d) => [doc, ...d]);
        setNotice(`"${file.name}" uploaded. Processing…`);
      } catch (e) {
        setError(`${file.name}: ${(e as Error).message}`);
      }
    }
    setUploading(false);
    if (fileInput.current) fileInput.current.value = "";
  }

  async function remove(doc: DocumentItem) {
    if (!window.confirm(`Delete "${doc.title}" and its embeddings?`)) return;
    try {
      await api.deleteDocument(doc.id);
      setDocs((d) => d.filter((x) => x.id !== doc.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const visible = docs.filter((d) => d.title.toLowerCase().includes(filter.toLowerCase()));
  const totalChunks = docs.reduce((n, d) => n + d.chunk_count, 0);

  return (
    <section className="documents">
      <header className="page-head">
        <div>
          <h2>Knowledge base</h2>
          <p className="muted">{docs.length} documents · {totalChunks.toLocaleString()} fragments</p>
        </div>
      </header>

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files); }}
        onClick={() => fileInput.current?.click()}
      >
        <input ref={fileInput} type="file" accept={ACCEPT} multiple hidden onChange={(e) => upload(e.target.files)} />
        <strong>{uploading ? "Uploading…" : "Drop files here or click to upload"}</strong>
        <span className="muted">PDF, TXT, Markdown, CSV or DOCX · max 50 MB</span>
      </div>

      {notice && <div className="alert ok">{notice}</div>}
      {error && <div className="alert error">{error}</div>}

      <input className="search" placeholder="Filter documents…" value={filter} onChange={(e) => setFilter(e.target.value)} />

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Title</th><th>Status</th><th>Fragments</th><th>Uploaded by</th><th>Date</th><th /></tr>
          </thead>
          <tbody>
            {visible.map((d) => (
              <tr key={d.id}>
                <td>
                  {d.source_url ? <a href={d.source_url} target="_blank" rel="noreferrer">{d.title}</a> : d.title}
                  <div className="muted small">{d.filename}</div>
                </td>
                <td><span className={`badge ${d.status}`} title={d.error ?? ""}>{d.status}</span></td>
                <td>{d.chunk_count}</td>
                <td>{d.uploaded_by_name}</td>
                <td>{new Date(d.created_at).toLocaleDateString()}</td>
                <td>{d.can_delete && <button className="btn danger small" onClick={() => remove(d)}>Delete</button>}</td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr><td colSpan={6} className="muted center">No documents yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
