import { CheckCircle2, XCircle, RotateCcw, Download, RefreshCw, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import type { VerificationResult } from '../types/api';

interface VerificationPanelProps {
  sessionId: string;
  verification: VerificationResult;
  canRetry: boolean;
  busyAction: string | null;
  onRollback: () => void;
  onRetryRepair: () => void;
  onReset: () => void;
}

export function VerificationPanel({
  sessionId,
  verification,
  canRetry,
  busyAction,
  onRollback,
  onRetryRepair,
  onReset,
}: VerificationPanelProps) {
  const verified = verification.verdict === 'REPAIR_VERIFIED';

  return (
    <div
      className={`space-y-4 rounded-2xl border p-5 ${
        verified
          ? 'border-emerald-500/50 bg-emerald-950/20'
          : 'border-rose-500/50 bg-rose-950/20'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {verified ? (
            <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-emerald-400" />
          ) : (
            <XCircle className="mt-0.5 h-6 w-6 shrink-0 text-rose-400" />
          )}
          <div>
            <h3 className="text-base font-bold text-white">
              {verified ? 'REPAIR VERIFIED — All Tests Pass' : `REPAIR FAILED (${verification.reason || 'Tests Failing'})`}
            </h3>
            <p className="mt-0.5 text-xs text-slate-300">
              Post-patch pytest run: <strong>{verification.passed} passed</strong>,{' '}
              <strong>{verification.failed} failed</strong>,{' '}
              <strong>{verification.errors} errors</strong> in {verification.duration_s.toFixed(2)}s
              {' · '}
              <strong>{verification.regressions.length} regressions</strong>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!verified && canRetry && (
            <button
              type="button"
              disabled={busyAction !== null}
              onClick={onRetryRepair}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
            >
              {busyAction === 'repair' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Retry Repair (Attempt 2)
            </button>
          )}
          <button
            type="button"
            disabled={busyAction !== null}
            onClick={onRollback}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            {busyAction === 'rollback' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RotateCcw className="h-3.5 w-3.5" />
            )}
            Rollback Patch
          </button>
          <button
            type="button"
            disabled={busyAction !== null}
            onClick={onReset}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            Reset Sandbox
          </button>
          <a
            href={api.reportDownloadUrl(sessionId, 'json')}
            download={`${sessionId}.json`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
          >
            <Download className="h-3.5 w-3.5" />
            JSON Report
          </a>
          <a
            href={api.reportDownloadUrl(sessionId, 'md')}
            download={`${sessionId}.md`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800"
          >
            <Download className="h-3.5 w-3.5" />
            Markdown Report
          </a>
        </div>
      </div>

      {verification.originally_failing_now_passing.length > 0 && (
        <div className="rounded-xl border border-emerald-500/30 bg-slate-950/60 p-3 text-xs">
          <span className="font-semibold text-emerald-300">Resolved Failing Tests:</span>
          <ul className="mt-1 list-inside list-disc font-mono text-slate-200">
            {verification.originally_failing_now_passing.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {verification.regressions.length > 0 && (
        <div className="rounded-xl border border-rose-500/30 bg-slate-950/60 p-3 text-xs">
          <span className="font-semibold text-rose-300">Regressions Detected:</span>
          <ul className="mt-1 list-inside list-disc font-mono text-rose-200">
            {verification.regressions.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
