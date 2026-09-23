"use client";

import { CheckCircle2, CircleDashed, AlertTriangle, XCircle, Workflow } from "lucide-react";
import clsx from "clsx";
import { AgentStep } from "@/lib/types";

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string; ring: string }> = {
  success: { icon: CheckCircle2, color: "text-emerald-400", ring: "ring-emerald-400/30" },
  warning: { icon: AlertTriangle, color: "text-amber-400", ring: "ring-amber-400/30" },
  error: { icon: XCircle, color: "text-rose-400", ring: "ring-rose-400/30" },
  running: { icon: CircleDashed, color: "text-accent2", ring: "ring-accent2/30" },
};

export default function AgentStepsTimeline({ steps }: { steps: AgentStep[] }) {
  if (!steps.length) {
    return (
      <div className="flex items-center gap-2 text-muted text-sm p-4">
        <Workflow size={16} />
        <span>Agent execution steps will appear here once you ask a question.</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2 px-4 pt-4 pb-2 text-xs uppercase tracking-wider text-muted">
        <Workflow size={14} />
        Agent Execution Trace
      </div>
      <ol className="relative px-4 pb-4">
        {steps.map((step, idx) => {
          const style = STATUS_STYLES[step.status] ?? STATUS_STYLES.running;
          const Icon = style.icon;
          const isLast = idx === steps.length - 1;
          return (
            <li key={`${step.step}-${idx}`} className="relative pl-8 pb-5 last:pb-0">
              {!isLast && (
                <span className="absolute left-[11px] top-6 bottom-0 w-px bg-border" aria-hidden />
              )}
              <span
                className={clsx(
                  "absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-surface2 ring-2",
                  style.ring
                )}
              >
                <Icon size={14} className={style.color} />
              </span>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-medium text-gray-100">{step.label}</p>
                <span className="text-[10px] font-mono text-muted shrink-0">
                  {new Date(step.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
              {step.detail && <p className="mt-0.5 text-xs text-muted leading-relaxed">{step.detail}</p>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
