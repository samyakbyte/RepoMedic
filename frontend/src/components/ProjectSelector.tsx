import { Bug, FileCode2, Play, Loader2 } from 'lucide-react';
import type { Project } from '../types/api';

interface ProjectSelectorProps {
  projects: Project[];
  activeProjectId?: string | null;
  busyAction: string | null;
  onStartProject: (projectId: string) => void;
}

export function ProjectSelector({
  projects,
  activeProjectId,
  busyAction,
  onStartProject,
}: ProjectSelectorProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Demo Repositories</h2>
          <p className="text-xs text-slate-400">
            Each run copies the selected project into an isolated sandbox under <code className="text-slate-300">data/workspaces/</code> — original fixtures are never modified.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {projects.map((p) => {
          const isSelected = activeProjectId === p.id;
          const isStarting = busyAction === `start:${p.id}`;
          return (
            <div
              key={p.id}
              className={`flex flex-col justify-between rounded-2xl border p-4 transition ${
                isSelected
                  ? 'border-emerald-500/60 bg-slate-900 shadow-lg shadow-emerald-950/30'
                  : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
              }`}
            >
              <div>
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-white">{p.name}</h3>
                  <span className="shrink-0 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                    {p.bug_category}
                  </span>
                </div>
                <p className="mb-3 text-xs leading-relaxed text-slate-400">{p.description}</p>

                <div className="space-y-1.5 rounded-xl border border-slate-800/80 bg-slate-950/60 p-2.5 text-[11px] font-mono">
                  <div className="flex items-center gap-1.5 text-rose-300">
                    <Bug className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                    <span className="truncate" title={p.failing_test}>
                      {p.failing_test}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <FileCode2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                    <span className="truncate">Allowlist: {p.target_files.join(', ')}</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                disabled={busyAction !== null}
                onClick={() => onStartProject(p.id)}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 px-3.5 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Creating Sandbox & Diagnosing...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5" />
                    {isSelected ? 'New Clean Session & Diagnose' : 'Select & Run Diagnostics'}
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
