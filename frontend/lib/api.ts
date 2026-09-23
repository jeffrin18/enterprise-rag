import { QueryResponse } from "./types";

export async function runQuery(question: string, sessionId?: string): Promise<QueryResponse> {
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId ?? null, top_k: 6 }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Query failed with status ${res.status}`);
  }
  return res.json();
}

export async function ingestDocument(sourcePath: string, docId?: string) {
  const res = await fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_path: sourcePath, doc_id: docId ?? null, metadata: {} }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Ingest failed with status ${res.status}`);
  }
  return res.json();
}
