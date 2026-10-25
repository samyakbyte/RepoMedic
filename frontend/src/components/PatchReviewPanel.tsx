import { useState } from 'react';
import {
  Check,
  X,
  ShieldCheck,
  ShieldAlert,
  Gauge,
  Clock,
  Sparkles,
  Loader2,
  Columns2,
  AlignJustify,
} from 'lucide-react';
import type { AttemptRecord, SessionState } from '../types/api';

interface PatchReviewPanelProps {
  attempt: AttemptRecord;
  sessionState: SessionState;
  busyAction: string | null;
  onApprove: () => void;
  onReject: (reason?: string) => void;
}

export function PatchReviewPanel({
  attempt,
  sessionState,
  busyAction,
  onApprove,
  onReject,
}: PatchReviewPanelProps) {
  const [viewMode, setViewMode] = useState<'unified' | 'split'>('unified');
  const [rejectNote, setRejectNote] = useState('');
  const { patch, validation, llm } = attempt;
  const awaitingApproval = sessionState === 'AWAITING_APPROVAL';

  const diffLines = (validation.diff || '').split('\n');

  return (
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">
              Proposed Repair — Attempt #{attempt.n}
            </h3>
            <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs text-emerald-300">
              {patch.target_file}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-300">
            <strong className="text-slate-400">Root Cause:</strong> {patch.root_cause}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {validation.ok ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 font-medium text-emerald-300">
              <ShieldCheck className="h-3.5 w-3.5" />
              AST + Allowlist Validated
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-2.5 py-1 font-medium text-rose-300">
              <ShieldAlert className="h-3.5 w-3.5" />
              Invalid: {validation.codes.join(', ')}
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-300">
            <Clock className="h-3.5 w-3.5 text-sky-400" />
            {llm.duration_s.toFixed(2)}s
          </span>
          {llm.tokens_per_second != null && (
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-300">
              <Gauge className="h-3.5 w-3.5 text-emerald-400" />
              {llm.tokens_per_second.toFixed(1)} tok/s
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 text-xs md:grid-cols-2">
        <div>
          <span className="font-semibold uppercase tracking-wider text-slate-400">Explanation</span>
          <p className="mt-1 leading-relaxed text-slate-200">{patch.explanation}</p>
        </div>
        <div>
          <span className="font-semibold uppercase tracking-wider text-slate-400">
            Expected Outcome
          </span>
          <p className="mt-1 leading-relaxed text-slate-200">{patch.expected_outcome}</p>
        </div>
      </div>

      {/* Diff Viewer */}
      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-800 px-3.5 py-2">
          <span className="font-mono text-xs text-slate-300">{patch.target_file}</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setViewMode('unified')}
              className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ${
                viewMode === 'unified'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <AlignJustify className="h-3 w-3" />
              Unified Diff
            </button>
            <button
              type="button"
              onClick={() => setViewMode('split')}
              className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ${
                viewMode === 'split'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Columns2 className="h-3 w-3" />
              Snippets
            </button>
          </div>
        </div>

        {viewMode === 'unified' ? (
          <div className="max-h-80 overflow-auto p-3 font-mono text-xs leading-relaxed">
            {diffLines.map((line, i) => {
              let lineCls = 'text-slate-300';
              if (line.startsWith('+++') || line.startsWith('---')) {
                lineCls = 'text-slate-400 font-semibold';
              } else if (line.startsWith('@@')) {
                lineCls = 'text-sky-400';
              } else if (line.startsWith('+')) {
                lineCls = 'bg-emerald-500/15 text-emerald-300';
              } else if (line.startsWith('-')) {
                lineCls = 'bg-rose-500/15 text-rose-300';
              }
              return (
                <div key={i} className={`whitespace-pre px-2 py-0.5 ${lineCls}`}>
                  {line || ' '}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid divide-y divide-slate-800 md:grid-cols-2 md:divide-x md:divide-y-0">
            <div className="p-3">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-rose-400">
                Removed (old_snippet)
              </div>
              <pre className="overflow-auto rounded-lg bg-rose-500/10 p-2.5 font-mono text-xs text-rose-200">
                {patch.old_snippet}
              </pre>
            </div>
            <div className="p-3">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-emerald-400">
                Added (new_snippet)
              </div>
              <pre className="overflow-auto rounded-lg bg-emerald-500/10 p-2.5 font-mono text-xs text-emerald-200">
                {patch.new_snippet}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Human-in-the-loop Approval Gate */}
      {awaitingApproval && (
        <div className="flex flex-col gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-300">
              Human Approval Gate
            </h4>
            <p className="mt-0.5 text-xs text-amber-100/90">
              No file is modified until you approve. Approving creates a SHA-256 backup, writes the patch atomically, and re-runs pytest.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              placeholder="Optional reject note..."
              className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:border-amber-400 focus:outline-none"
            />
            <button
              type="button"
              disabled={busyAction !== null}
              onClick={() => onReject(rejectNote || undefined)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-500/15 px-3.5 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/25 disabled:opacity-50"
            >
              {busyAction === 'reject' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <X className="h-3.5 w-3.5" />
              )}
              Reject
            </button>
            <button
              type="button"
              disabled={busyAction !== null || !validation.ok}
              onClick={onApprove}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 shadow-sm transition hover:bg-emerald-400 disabled:opacity-50"
            >
              {busyAction === 'approve' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5" />
              )}
              Approve & Verify with Pytest
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
