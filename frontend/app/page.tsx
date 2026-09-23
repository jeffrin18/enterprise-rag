"use client";

import { useState } from "react";
import { BrainCircuit } from "lucide-react";
import ChatInterface from "@/components/ChatInterface";
import AgentStepsTimeline from "@/components/AgentStepsTimeline";
import GraphVisualizer from "@/components/GraphVisualizer";
import { QueryResponse } from "@/lib/types";

export default function Home() {
  const [lastResult, setLastResult] = useState<QueryResponse | null>(null);

  return (
    <main className="h-screen flex flex-col bg-canvas">
      <header className="flex items-center gap-3 px-6 py-4 border-b border-border">
        <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-accent/20 text-accent">
          <BrainCircuit size={20} />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-gray-100">
            Agentic Enterprise Knowledge Graph & Multi-Source RAG
          </h1>
          <p className="text-xs text-muted">Router Agent · Self-Correction Loop · Graph-RAG</p>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_380px] overflow-hidden">
        <section className="border-r border-border overflow-hidden">
          <ChatInterface onResult={setLastResult} />
        </section>

        <aside className="flex flex-col overflow-y-auto divide-y divide-border">
          <div className="min-h-[280px]">
            <AgentStepsTimeline steps={lastResult?.agent_steps ?? []} />
          </div>
          <div className="min-h-[320px] flex-1">
            <GraphVisualizer subgraph={lastResult?.subgraph ?? { nodes: [], edges: [] }} />
          </div>
        </aside>
      </div>
    </main>
  );
}
