import { useEffect, useRef } from 'react';
import anime from 'animejs';
import { Check, Loader2, AlertTriangle, XCircle } from 'lucide-react';
import { WORKING_STATES, type SessionState } from '../types/api';

interface StatePipelineProps {
  state: SessionState;
  attempt: number;
  maxAttempts: number;
}

const STEPS: { key: string; label: string; match: SessionState[] }[] = [
  { key: 'diagnose', label: '1. Diagnose', match: ['DIAGNOSING'] },
  { key: 'failure', label: '2. Failure Detected', match: ['FAILURE_DETECTED'] },
  { key: 'generate', label: '3. Propose Patch', match: ['GENERATING_REPAIR', 'PATCH_READY'] },
  { key: 'approval', label: '4. Human Review', match: ['AWAITING_APPROVAL'] },
  { key: 'verify', label: '5. Apply & Verify', match: ['APPLYING_PATCH', 'VERIFYING'] },
  { key: 'verdict', label: '6. Verdict', match: ['REPAIR_VERIFIED', 'REPAIR_FAILED'] },
];

const STATE_RANK: Record<SessionState, number> = {
  IDLE: -1,
  DIAGNOSING: 0,
  FAILURE_DETECTED: 1,
  GENERATING_REPAIR: 2,
  PATCH_READY: 2,
  AWAITING_APPROVAL: 3,
  APPLYING_PATCH: 4,
  VERIFYING: 4,
  REPAIR_VERIFIED: 5,
  REPAIR_FAILED: 5,
  ERROR: -2,
};

export function stateBadgeStyle(state: SessionState): string {
  switch (state) {
    case 'REPAIR_VERIFIED':
      return 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300';
    case 'REPAIR_FAILED':
    case 'ERROR':
      return 'border-rose-500/40 bg-rose-500/15 text-rose-300';
    case 'AWAITING_APPROVAL':
      return 'border-amber-500/40 bg-amber-500/15 text-amber-300';
    case 'FAILURE_DETECTED':
      return 'border-orange-500/40 bg-orange-500/15 text-orange-300';
    case 'DIAGNOSING':
    case 'GENERATING_REPAIR':
    case 'APPLYING_PATCH':
    case 'VERIFYING':
      return 'border-sky-500/40 bg-sky-500/15 text-sky-300';
    default:
      return 'border-slate-700 bg-slate-800 text-slate-300';
  }
}

export function StatePipeline({ state, attempt, maxAttempts }: StatePipelineProps) {
  const barRef = useRef<HTMLDivElement | null>(null);
  const rank = STATE_RANK[state] ?? -1;
  const isWorking = WORKING_STATES.has(state);

  useEffect(() => {
    if (!barRef.current) return;
    anime({
      targets: barRef.current.querySelectorAll('.step-node'),
      scale: [0.96, 1],
      opacity: [0.85, 1],
      duration: 280,
      easing: 'easeOutQuad',
    });
  }, [state]);

  return (
    <div ref={barRef} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Session State
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${stateBadgeStyle(
              state
            )}`}
          >
            {isWorking && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {state}
          </span>
        </div>
        <span className="text-xs font-medium text-slate-400">
          Repair Attempt:{' '}
          <strong className="text-slate-200">
            {attempt} / {maxAttempts}
          </strong>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {STEPS.map((step, idx) => {
          const active = step.match.includes(state);
          const done = rank > idx || state === 'REPAIR_VERIFIED';
          const failedHere = idx === 5 && state === 'REPAIR_FAILED';

          let cls = 'border-slate-800 bg-slate-950/60 text-slate-500';
          if (failedHere) {
            cls = 'border-rose-500/50 bg-rose-500/10 text-rose-300';
          } else if (active) {
            cls =
              state === 'REPAIR_VERIFIED'
                ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-200'
                : state === 'AWAITING_APPROVAL'
                ? 'border-amber-500/50 bg-amber-500/15 text-amber-200'
                : 'border-sky-500/50 bg-sky-500/15 text-sky-200';
          } else if (done) {
            cls = 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
          }

          return (
            <div
              key={step.key}
              className={`step-node flex items-center justify-between rounded-xl border px-3 py-2 text-xs font-medium transition ${cls}`}
            >
              <span className="truncate">{step.label}</span>
              {failedHere ? (
                <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
              ) : active && isWorking ? (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-sky-400" />
              ) : done ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
              ) : null}
            </div>
          );
        })}
      </div>

      {state === 'ERROR' && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>
            Session encountered an error (check the latest timeline entry below or ensure Ollama is running with the model pulled). You can retry repair or reset the workspace.
          </span>
        </div>
      )}
    </div>
  );
}
