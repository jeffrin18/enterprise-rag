export type RetrievalRoute = "vector_search" | "graph_traversal" | "structured_sql" | "hybrid";

export interface RetrievedChunk {
  chunk_id: string;
  text: string;
  score: number;
  source: RetrievalRoute;
  metadata: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphSubgraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CritiqueVerdict {
  faithfulness_score: number;
  context_recall_score: number;
  hallucination_detected: boolean;
  missing_information: string[];
  verdict: "accept" | "retry";
  retry_instructions?: string | null;
}

export type AgentStepStatus = "running" | "success" | "warning" | "error";

export interface AgentStep {
  step: string;
  label: string;
  status: AgentStepStatus;
  detail?: string | null;
  timestamp: number;
}

export interface QueryResponse {
  answer: string;
  session_id?: string | null;
  route_taken: RetrievalRoute;
  retrieved_chunks: RetrievedChunk[];
  subgraph: GraphSubgraph;
  critique?: CritiqueVerdict | null;
  agent_steps: AgentStep[];
  self_corrections: number;
  guardrail_flags: string[];
}
