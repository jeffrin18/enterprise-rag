"use client";

import { useState } from "react";
import { Send, ShieldAlert, RefreshCcw, BadgeCheck, Database, Network, Table2, Layers } from "lucide-react";
import clsx from "clsx";
import { runQuery } from "@/lib/api";
import { QueryResponse } from "@/lib/types";

const ROUTE_META: Record<string, { icon: typeof Database; label: string }> = {
  vector_search: { icon: Database, label: "Vector Search" },
  graph_traversal: { icon: Network, label: "Graph Traversal" },
  structured_sql: { icon: Table2, label: "Structured SQL" },
  hybrid: { icon: Layers, label: "Hybrid" },
};

export default function ChatInterface({ onResult }: { onResult: (r: QueryResponse) => void }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<{ question: string; response: QueryResponse }[]>([]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await runQuery(question.trim());
      setHistory((h) => [...h, { question: question.trim(), response }]);
      onResult(response);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-6">
        {history.length === 0 && !loading && (
          <div className="text-muted text-sm max-w-md">
            Ask a question about your ingested documents. The Router Agent will decide whether to use
            vector search, graph traversal, structured SQL, or a hybrid of these — then a Critique Agent
            checks the answer for faithfulness before returning it.
          </div>
        )}

        {history.map((turn, idx) => {
          const meta = ROUTE_META[turn.response.route_taken] ?? ROUTE_META.vector_search;
          const RouteIcon = meta.icon;
          const critique = turn.response.critique;
          return (
            <div key={idx} className="flex flex-col gap-3">
              <div className="self-end max-w-xl rounded-2xl rounded-br-sm bg-accent/15 border border-accent/30 px-4 py-2.5 text-sm text-gray-100">
                {turn.question}
              </div>

              <div className="self-start max-w-2xl rounded-2xl rounded-bl-sm bg-surface border border-border px-4 py-3 text-sm text-gray-100 flex flex-col gap-3">
                <p className="leading-relaxed whitespace-pre-wrap">{turn.response.answer}</p>

                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/60">
                  <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full bg-surface2 text-accent2 border border-accent2/20">
                    <RouteIcon size={12} /> {meta.label}
                  </span>

                  {turn.response.self_corrections > 0 && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20">
                      <RefreshCcw size={12} /> {turn.response.self_corrections} self-correction
                      {turn.response.self_corrections > 1 ? "s" : ""}
                    </span>
                  )}

                  {critique && (
                    <span
                      className={clsx(
                        "inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full border",
                        critique.hallucination_detected
                          ? "bg-rose-400/10 text-rose-400 border-rose-400/20"
                          : "bg-emerald-400/10 text-emerald-400 border-emerald-400/20"
                      )}
                    >
                      <BadgeCheck size={12} />
                      faithfulness {critique.faithfulness_score.toFixed(2)} · recall{" "}
                      {critique.context_recall_score.toFixed(2)}
                    </span>
                  )}

                  {turn.response.guardrail_flags.length > 0 && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full bg-surface2 text-muted border border-border">
                      <ShieldAlert size={12} /> {turn.response.guardrail_flags.length} guardrail flag
                      {turn.response.guardrail_flags.length > 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {turn.response.retrieved_chunks.length > 0 && (
                  <details className="text-xs text-muted">
                    <summary className="cursor-pointer hover:text-gray-300">
                      {turn.response.retrieved_chunks.length} retrieved context chunk
                      {turn.response.retrieved_chunks.length > 1 ? "s" : ""}
                    </summary>
                    <div className="mt-2 flex flex-col gap-2">
                      {turn.response.retrieved_chunks.slice(0, 5).map((c) => (
                        <div key={c.chunk_id} className="rounded-lg bg-surface2 border border-border p-2">
                          <div className="flex justify-between text-[10px] text-muted mb-1">
                            <span className="font-mono">{c.chunk_id}</span>
                            <span>score {c.score.toFixed(2)}</span>
                          </div>
                          <p className="line-clamp-3">{c.text}</p>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="self-start max-w-2xl rounded-2xl rounded-bl-sm bg-surface border border-border px-4 py-3 text-sm text-muted animate-pulse">
            Routing query, retrieving context, generating and self-evaluating the answer…
          </div>
        )}

        {error && (
          <div className="self-start max-w-2xl rounded-2xl bg-rose-400/10 border border-rose-400/30 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-border p-4 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your ingested documents…"
          className="flex-1 rounded-xl bg-surface border border-border px-4 py-2.5 text-sm text-gray-100 placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent/90 transition"
        >
          <Send size={16} /> Ask
        </button>
      </form>
    </div>
  );
}
