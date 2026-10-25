import { AlertCircle, Sparkles, Play, RotateCcw, Loader2, Terminal } from 'lucide-react';
import { ProjectSelector } from '../components/ProjectSelector';
import { StatePipeline } from '../components/StatePipeline';
import { DiagnosticsPanel } from '../components/DiagnosticsPanel';
import { PatchReviewPanel } from '../components/PatchReviewPanel';
import { VerificationPanel } from '../components/VerificationPanel';
import { TimelinePanel } from '../components/TimelinePanel';
import type { UiError } from '../hooks/useRepoMedic';
import {
  WORKING_STATES,
  type ModelStatus,
  type Project,
  type SessionDetail,
} from '../types/api';

interface RepairStudioPageProps {
  projects: Project[];
  activeSession: SessionDetail | null;
  sessionFiles: Record<string, string>;
  modelStatus: ModelStatus | null;
  busyAction: string | null;
  uiError: UiError | null;
  onClearError: () => void;
  onStartProject: (projectId: string) => void;
  onDiagnose: () => void;
  onRepair: () => void;
  onApprove: () => void;
  onReject: (reason?: string) => void;
  onRollback: () => void;
  onReset: () => void;
}

export function RepairStudioPage({
  projects,
  activeSession,
  sessionFiles,
  modelStatus,
  busyAction,
  uiError,
  onClearError,
  onStartProject,
  onDiagnose,
  onRepair,
  onApprove,
  onReject,
  onRollback,
  onReset,
}: RepairStudioPageProps) {
  const ollamaReady = Boolean(modelStatus?.ollama_reachable && modelStatus?.model_available);
  const latestAttempt =
    activeSession && activeSession.attempts.length > 0
      ? activeSession.attempts[activeSession.attempts.length - 1]
      : null;

  const canGenerateRepair =
    activeSession &&
    (activeSession.state === 'FAILURE_DETECTED' ||
      activeSession.state === 'REPAIR_FAILED' ||
      activeSession.state === 'ERROR') &&
    activeSession.attempt < activeSession.max_attempts;

  return (
    <div className="space-y-6">
      {/* Ollama offline / model missing guidance banner */}
      {modelStatus && !ollamaReady && (
        <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-100">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-semibold text-amber-300">
              <Terminal className="h-4 w-4" />
              {modelStatus.ollama_reachable
                ? `Local model "${modelStatus.model}" is not pulled yet`
                : 'Local Ollama service is offline — Pytest Diagnostics still work!'}
            </div>
            <p className="text-amber-200/90">
              {modelStatus.hint ||
                `Run "ollama serve" and "ollama pull ${modelStatus.model}" in a terminal to enable offline AI patch generation.`}
            </p>
          </div>
          <code className="rounded-lg bg-slate-950/80 px-3 py-1.5 font-mono text-[11px] text-amber-300">
            ollama pull {modelStatus.model}
          </code>
        </div>
      )}

      {uiError && (
        <div className="flex items-start justify-between gap-3 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-100">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <div>
              <div className="font-semibold text-rose-300">[{uiError.code}] {uiError.message}</div>
              {uiError.hint && <p className="mt-0.5 text-rose-200/80">{uiError.hint}</p>}
            </div>
          </div>
          <button
            type="button"
            onClick={onClearError}
            className="rounded-md px-2 py-1 text-rose-300 hover:bg-rose-500/20"
          >
            Dismiss
          </button>
        </div>
      )}

      <ProjectSelector
        projects={projects}
        activeProjectId={activeSession?.project_id}
        busyAction={busyAction}
        onStartProject={onStartProject}
      />

      {activeSession && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-slate-400">Active Session:</span>
              <code className="rounded bg-slate-800 px-2 py-0.5 font-mono text-emerald-300">
                {activeSession.id}
              </code>
              <span className="text-slate-500">·</span>
              <span className="font-medium text-white">{activeSession.project_id}</span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {activeSession.state === 'IDLE' && (
                <button
                  type="button"
                  disabled={busyAction !== null}
                  onClick={onDiagnose}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-sky-500 px-3.5 py-2 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
                >
                  {busyAction === 'diagnose' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )}
                  Run Diagnostics
                </button>
              )}

              {canGenerateRepair && (
                <button
                  type="button"
                  disabled={busyAction !== null || WORKING_STATES.has(activeSession.state)}
                  onClick={onRepair}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 shadow-sm hover:bg-emerald-400 disabled:opacity-50"
                >
                  {busyAction === 'repair' || activeSession.state === 'GENERATING_REPAIR' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  Generate Repair Proposal (Attempt {activeSession.attempt + 1}/{activeSession.max_attempts})
                </button>
              )}

              <button
                type="button"
                disabled={busyAction !== null || WORKING_STATES.has(activeSession.state)}
                onClick={onReset}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reset Session
              </button>
            </div>
          </div>

          <StatePipeline
            state={activeSession.state}
            attempt={activeSession.attempt}
            maxAttempts={activeSession.max_attempts}
          />

          {latestAttempt?.verification && (
            <VerificationPanel
              sessionId={activeSession.id}
              verification={latestAttempt.verification}
              canRetry={activeSession.attempt < activeSession.max_attempts}
              busyAction={busyAction}
              onRollback={onRollback}
              onRetryRepair={onRepair}
              onReset={onReset}
            />
          )}

          {latestAttempt && (
            <PatchReviewPanel
              attempt={latestAttempt}
              sessionState={activeSession.state}
              busyAction={busyAction}
              onApprove={onApprove}
              onReject={onReject}
            />
          )}

          {activeSession.diagnostics_before && (
            <DiagnosticsPanel
              diagnostics={activeSession.diagnostics_before}
              files={sessionFiles}
            />
          )}

          <TimelinePanel timeline={activeSession.timeline} />
        </div>
      )}
    </div>
  );
}
