import { CornerDownLeft } from "lucide-react";
import { useState } from "react";
import { fetchQueryPlan, type QueryPlanDto } from "@/lib/lunarbit/api";

export function QueryConsole() {
  const [question, setQuestion] = useState("");
  const [plan, setPlan] = useState<QueryPlanDto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim().slice(0, 500);
    if (!q) return;
    setBusy(true);
    setError(null);
    fetchQueryPlan(q)
      .then(setPlan)
      .catch(() => setError("planner unavailable"))
      .finally(() => setBusy(false));
  };

  return (
    <div className="panel glow-ring w-[27rem] p-3">
      <form onSubmit={submit} className="flex items-center gap-2">
        <span className="label-mono">ask</span>
        <input
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="why did delivery fees exceed declared scope?"
          className="flex-1 bg-transparent font-mono text-xs text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
        />
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-sm border border-border px-2 py-1 font-mono text-[0.6rem] uppercase tracking-widest text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          {busy ? "…" : "plan"} <CornerDownLeft className="size-3" />
        </button>
      </form>

      {plan && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          <div className="flex flex-wrap gap-1.5">
            {plan.selected_tools.map((t) => (
              <span
                key={t}
                className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-[0.6rem] text-muted-foreground"
              >
                {t}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[
              ["intent", plan.intent.replace(/_/g, " ")],
              ["actions", `${plan.actions.length}/${plan.action_budget}`],
              ["depth", String(plan.maximum_depth)],
              ["verify", plan.verification_required ? "required" : "off"],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="label-mono">{k}</div>
                <div className="truncate font-mono text-[0.65rem]">{v}</div>
              </div>
            ))}
          </div>
          {error && <p className="font-mono text-[0.6rem] text-destructive">{error}</p>}
        </div>
      )}
    </div>
  );
}
