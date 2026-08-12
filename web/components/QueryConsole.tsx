"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";
import { reviewedDemoAnswer } from "@/lib/demo-answer";

interface AskEventDetail { question?: string }

export function openQueryConsole(question?: string) {
  window.dispatchEvent(new CustomEvent<AskEventDetail>("lunarbit:ask", { detail: { question } }));
}

export function QueryConsole() {
  const { dataProfile } = useProfiles();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState(dataProfile.questions[0] ?? "");
  const [submitted, setSubmitted] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const answer = submitted ? reviewedDemoAnswer(dataProfile, submitted) : null;

  useEffect(() => {
    const onAsk = (event: Event) => {
      const detail = (event as CustomEvent<AskEventDetail>).detail;
      if (detail?.question) {
        setQuestion(detail.question);
        setSubmitted(detail.question);
      }
      setOpen(true);
    };
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("lunarbit:ask", onAsk);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("lunarbit:ask", onAsk);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalized = question.trim();
    if (normalized.length >= 3) setSubmitted(normalized);
  };

  if (!open) return null;

  return (
    <div className="query-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section aria-label="Ask Lunarbit" aria-modal="true" className="query-console" role="dialog">
        <header className="query-console-header"><div><span>QUERY CONTROL / {dataProfile.handle}</span><h2>Ask the evidence graph</h2></div><button aria-label="Close query console" onClick={() => setOpen(false)} type="button">ESC</button></header>
        <form className="query-form" onSubmit={submit}><Icon name="spark" /><input aria-label="Commerce question" maxLength={500} onChange={(event) => setQuestion(event.target.value)} ref={inputRef} value={question} /><button type="submit">RUN <Icon name="arrow" /></button></form>
        <div className="query-presets"><span>REVIEWED SYNTHETIC QUESTIONS</span><div>{dataProfile.questions.map((value, index) => <button key={value} onClick={() => { setQuestion(value); setSubmitted(value); }} type="button"><i>Q{index + 1}</i>{value}</button>)}</div></div>
        {answer && <div className={`answer-console ${answer.status}`}>
          <div className="execution-rail">{["ROUTE", "RETRIEVE", "EXPAND", "VERIFY"].map((value, index) => <span key={value}><i>{index + 1}</i><b>{value}</b><small>{answer.status === "verified" || index < 2 ? "PASS" : "ABSTAIN"}</small></span>)}</div>
          <article className="answer-body"><header><span>{answer.status.toUpperCase()} / {answer.confidence}</span><b>{answer.status === "verified" ? "EVIDENCE COMPLETE" : "ANSWER WITHHELD"}</b></header>{answer.directAnswer ? <><h3>{answer.directAnswer}</h3><div className="answer-calculation">{answer.calculation}</div></> : <h3>The requested claim is outside the reviewed public projection.</h3>}<div className="answer-meta"><div><span>GRAPH PATH</span><p>{answer.graphPath.length ? answer.graphPath.map((node) => node.split(":").at(-1)).join(" → ") : "No private traversal executed"}</p></div><div><span>EVIDENCE</span><p>{answer.evidence.length ? answer.evidence.join(" · ") : "No publishable evidence pack"}</p></div></div><footer>{answer.limitations.map((value) => <p key={value}>{value}</p>)}</footer></article>
        </div>}
      </section>
    </div>
  );
}
