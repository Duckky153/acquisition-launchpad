import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { CheckIcon, ChevronIcon, ShieldIcon } from "./Icons";

export type DemoAnchor = "overview" | "entities" | "mapping" | "blockers" | "sequence" | "audit";

interface DemoMissionProps {
  approvedCount: number;
  totalCount: number;
  isReady: boolean;
  onReviewDecision: () => void;
  onStartTour: () => void;
}

export function DemoMission({ approvedCount, totalCount, isReady, onReviewDecision, onStartTour }: DemoMissionProps): React.ReactElement {
  return (
    <section className={`demo-mission${isReady ? " is-complete" : ""}`} data-demo-anchor="overview" aria-labelledby="demo-mission-heading">
      <div className="demo-mission__lead">
        <p className="eyebrow">Three-minute recruiter demo</p>
        <h2 id="demo-mission-heading">{isReady ? "The acquisition package is ready" : "One decision turns the package ready"}</h2>
        <p>{isReady ? "The final human mapping is approved, the blocker is cleared, and every launch step is complete." : "Seventeen synthetic mapping decisions are already recorded. Review one final account to see evidence, controls, readiness, sequence, and audit history change together."}</p>
        <div className="demo-mission__actions">
          <button className="button button--demo" onClick={onReviewDecision} type="button">{isReady ? "Inspect final decision" : "Review final decision"}<ChevronIcon /></button>
          <button className="button button--demo-secondary" onClick={onStartTour} type="button">Start full tour</button>
        </div>
      </div>
      <dl className="demo-mission__story">
        <div><dt>Problem</dt><dd>Three acquired companies call the same accounts by different names.</dd></div>
        <div><dt>User</dt><dd>An implementation specialist and controller preparing finance data.</dd></div>
        <div><dt>Outcome</dt><dd>One standard chart, tied balances, no blockers, and a defensible audit trail.</dd></div>
      </dl>
      <div className="demo-mission__meter" aria-label={`${approvedCount} of ${totalCount} source accounts approved`}>
        <span><strong>{approvedCount}/{totalCount}</strong> approved</span>
        <div><i style={{ width: `${totalCount === 0 ? 0 : Math.round((approvedCount / totalCount) * 100)}%` }} /></div>
        <small>{isReady ? "Ready for the Phase 1 onboarding sequence" : "HZ-115 · Trade Receivables is the final decision"}</small>
      </div>
    </section>
  );
}

interface GuidedDemoProps {
  open: boolean;
  approvedCount: number;
  totalCount: number;
  openBlockerCount: number;
  isReady: boolean;
  onClose: () => void;
  onNavigate: (anchor: DemoAnchor, requestId: number) => void;
  onOpenAudit: () => void;
  startAt: "overview" | "mapping";
}

interface DemoStep {
  anchor: DemoAnchor;
  eyebrow: string;
  title: string;
  body: string;
  proof: string;
}

function buildSteps(isReady: boolean, openBlockerCount: number): [DemoStep, ...DemoStep[]] {
  return [
    {
      anchor: "overview",
      eyebrow: "1 · The problem",
      title: "Acquired companies rarely speak one accounting language",
      body: "Horizon bought two businesses. Their legacy systems use names like Trade Receivables, Tenant Receivables, and Customer A/R for the same kind of account.",
      proof: "The tool standardizes those names without changing a penny of the opening balances.",
    },
    {
      anchor: "entities",
      eyebrow: "2 · The user",
      title: "An implementation specialist controls the onboarding",
      body: "The entity rail shows the parent-child structure, source system, account count, and exact trial-balance status for each acquired company.",
      proof: "All three synthetic entities tie exactly before any readiness claim is made.",
    },
    {
      anchor: "mapping",
      eyebrow: "3 · Human evidence review",
      title: isReady ? "The final mapping is approved" : "Review the one decision left",
      body: "Open HZ-115. The system suggests Accounts Receivable and explains why, but confidence cannot approve it. A person must inspect and sign the decision.",
      proof: isReady ? "The recorded reviewer, note, target, and row version remain visible." : "Use Review & approve, identify yourself truthfully, and record what you inspected.",
    },
    {
      anchor: "blockers",
      eyebrow: "4 · Control consequence",
      title: isReady ? "The evidence-backed blocker cleared" : "One missing decision blocks readiness",
      body: "Blockers are derived from source evidence. There is no bypass button for a system-generated exception.",
      proof: isReady ? "There are no open blockers after the final mapping decision." : `${openBlockerCount} open blocker remains and points to HZ-115.`,
    },
    {
      anchor: "sequence",
      eyebrow: "5 · Operational outcome",
      title: isReady ? "Every dependency step is complete" : "The launch order shows what can happen next",
      body: "The dependency plan sequences intake, account mapping, tie-out, blocker resolution, and data-preparation readiness across the parent and children.",
      proof: "The plan is recalculated from the same deterministic evidence—not from presentation-layer status labels.",
    },
    {
      anchor: "audit",
      eyebrow: "6 · Defensible proof",
      title: "Every decision has a tamper-evident history",
      body: "The audit ledger records the human decision followed by blocker, readiness, sequence, and control-state events in a SHA-256 hash chain.",
      proof: "Open the ledger to inspect actor, timestamp, payload, previous hash, and event hash.",
    },
  ];
}

export function GuidedDemo({
  open,
  approvedCount,
  totalCount,
  openBlockerCount,
  isReady,
  onClose,
  onNavigate,
  onOpenAudit,
  startAt,
}: GuidedDemoProps): React.ReactElement | null {
  const initialStepIndex = startAt === "mapping" ? 2 : 0;
  const [stepIndex, setStepIndex] = useState(initialStepIndex);
  const requestId = useRef(0);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const steps = buildSteps(isReady, openBlockerCount);
  const step = steps[stepIndex] ?? steps[0];

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setStepIndex(initialStepIndex);
    const focusTimeout = window.setTimeout(() => headingRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(focusTimeout);
      returnFocusRef.current?.focus();
    };
  }, [initialStepIndex, open]);

  useEffect(() => {
    if (!open) return;
    requestId.current += 1;
    onNavigate(step.anchor, requestId.current);
  }, [onNavigate, open, step.anchor]);

  if (!open) return null;

  const goTo = (next: number): void => {
    setStepIndex(Math.min(Math.max(next, 0), steps.length - 1));
  };

  const dismiss = (): void => {
    setStepIndex(0);
    onClose();
  };

  const handleKeys = (event: KeyboardEvent<HTMLElement>): void => {
    if (event.key === "Escape") {
      event.preventDefault();
      dismiss();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      goTo(stepIndex + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      goTo(stepIndex - 1);
    }
  };

  return (
    <aside className="guided-demo" aria-label="Three-minute guided demo" onKeyDown={handleKeys} tabIndex={-1}>
      <div className="guided-demo__topline">
        <span><ShieldIcon /> Guided product story</span>
        <button aria-label="Dismiss guided demo" className="guided-demo__close" onClick={dismiss} type="button">Close</button>
      </div>
      <div className="guided-demo__progress" aria-label={`Step ${stepIndex + 1} of ${steps.length}`}>
        {steps.map((item, index) => (
          <button aria-current={index === stepIndex ? "step" : undefined} aria-label={`Go to ${item.eyebrow}`} className={index <= stepIndex ? "is-reached" : ""} key={item.anchor} onClick={() => goTo(index)} type="button"><span>{index + 1}</span></button>
        ))}
      </div>
      <div className="guided-demo__content">
        <p className="eyebrow">{step.eyebrow}</p>
        <h2 ref={headingRef} tabIndex={-1}>{step.title}</h2>
        <p>{step.body}</p>
        <div className="guided-demo__proof"><CheckIcon /><span>{step.proof}</span></div>
      </div>
      <div className="guided-demo__actions">
        <button className="button button--quiet" disabled={stepIndex === 0} onClick={() => goTo(stepIndex - 1)} type="button">Back</button>
        <button className="guided-demo__restart" onClick={() => goTo(0)} type="button">Restart guide</button>
        {step.anchor === "audit" ? (
          <button className="button button--primary" onClick={onOpenAudit} type="button">Open audit ledger</button>
        ) : (
          <button className="button button--primary" onClick={() => goTo(stepIndex + 1)} type="button">Next <span className="sr-only">guided demo step</span><ChevronIcon /></button>
        )}
      </div>
      <p className="guided-demo__hint">Keyboard: Left/Right steps · Esc closes</p>
      <div className="sr-only" aria-live="polite">Step {stepIndex + 1} of {steps.length}: {step.title}. {approvedCount} of {totalCount} mappings approved.</div>
    </aside>
  );
}
