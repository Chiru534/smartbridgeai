import { Database } from "lucide-react";

import { AIChatPanel } from "./AIChatPanel";

export function SqlAgentPanel() {
    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-primary/10 rounded-xl">
                    <Database className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">SQL Agent</h2>
                    <p className="text-sm text-muted-foreground mt-1">Read-only schema exploration and SQL execution with row limits and guardrails.</p>
                </div>
            </div>
            <div className="rounded-2xl border border-border/40 bg-amber-500/5 px-4 py-3 text-sm text-muted-foreground mb-6">
                The SQL agent is restricted to read-only queries. It inspects schema first, enforces row limits, and blocks mutating statements.
            </div>
            <div className="min-h-[720px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                <AIChatPanel mode="sql_agent" title="SQL Analyst" />
            </div>
        </div>
    );
}
