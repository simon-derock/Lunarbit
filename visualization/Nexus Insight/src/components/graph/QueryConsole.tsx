import { CornerDownLeft } from "lucide-react";
import { useState } from "react";
import { fetchPublicShowcaseAnswer, type PublicShowcaseAnswerDto } from "@/lib/lunarbit/api";

export function QueryConsole() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<PublicShowcaseAnswerDto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim().slice(0, 500);
    if (!q) return;
    setBusy(true);
    setError(null);
    fetchPublicShowcaseAnswer(q)
      .then(setResult)
      .catch(() => setError("public answer service unavailable"))
      .finally(() => setBusy(false));
  };

  const plan = result?.plan;
  const answer = result?.answer;

  return (
    <div className="panel glow-ring w-[27rem] p-3">
      <form onSubmit={submit} className="flex items-center gap-2">
        <span className="label-mono">ask</span>
        <input
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="did discounts offset platform and delivery fees?"
          className="flex-1 bg-transparent font-mono text-xs text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
        />
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-sm border border-border px-2 py-1 font-mono text-[0.6rem] uppercase tracking-widest text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          {busy ? "…" : "trace"} <CornerDownLeft className="size-3" />
        </button>
      </form>

      {plan && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          <div className="flex items-center justify-between gap-3">
            <span className="label-mono">
              {result?.status === "verified" ? "verified trace" : "abstained"}
            </span>
            <span className="font-mono text-[0.55rem] text-muted-foreground">
              synthetic showcase only
            </span>
          </div>
          {answer ? (
            <div className="space-y-1.5 border-l border-primary/60 pl-2.5">
              <p className="text-xs leading-relaxed text-foreground">{answer.direct_answer}</p>
              <p className="font-mono text-[0.6rem] leading-relaxed text-primary/90">
                {answer.calculation}
              </p>
              <p className="font-mono text-[0.55rem] leading-relaxed text-muted-foreground">
                {answer.graph_path.join(" → ")}
              </p>
              {answer.evidence.map((evidence) => (
                <p key={evidence.id} className="font-mono text-[0.55rem] text-muted-foreground">
                  evidence · {evidence.title} · {evidence.authority}
                </p>
              ))}
            </div>
          ) : (
            <p className="font-mono text-[0.6rem] leading-relaxed text-muted-foreground">
              {result?.limitations[0]}
            </p>
          )}
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
        </div>
      )}
      {error && <p className="mt-3 font-mono text-[0.6rem] text-destructive">{error}</p>}
    </div>
  );
}
