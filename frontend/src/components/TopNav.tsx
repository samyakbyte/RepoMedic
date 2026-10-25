import { Activity, BarChart3, CheckCircle2, Cpu, History, ShieldAlert, Wrench } from 'lucide-react';
import type { ModelStatus } from '../types/api';

export type NavTab = 'studio' | 'benchmarks' | 'history';

interface TopNavProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  modelStatus: ModelStatus | null;
  backendOnline: boolean;
  sessionCount: number;
}

export function TopNav({
  activeTab,
  onSelectTab,
  modelStatus,
  backendOnline,
  sessionCount,
}: TopNavProps) {
  const ollamaReady = Boolean(modelStatus?.ollama_reachable && modelStatus?.model_available);
  const ollamaReachableOnly = Boolean(modelStatus?.ollama_reachable && !modelStatus?.model_available);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-white">RepoMedic</span>
              <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-slate-300">
                Offline Agent
              </span>
            </div>
            <p className="text-xs text-slate-400">Diagnose. Patch. Verify. — Local pytest repair</p>
          </div>
        </div>

        <nav className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-900/80 p-1">
          <button
            type="button"
            onClick={() => onSelectTab('studio')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
              activeTab === 'studio'
                ? 'bg-emerald-500 text-slate-950 shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Wrench className="h-4 w-4" />
            Repair Studio
          </button>
          <button
            type="button"
            onClick={() => onSelectTab('benchmarks')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
              activeTab === 'benchmarks'
                ? 'bg-emerald-500 text-slate-950 shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            Benchmarks
          </button>
          <button
            type="button"
            onClick={() => onSelectTab('history')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
              activeTab === 'history'
                ? 'bg-emerald-500 text-slate-950 shadow-sm'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <History className="h-4 w-4" />
            Sessions
            {sessionCount > 0 && (
              <span
                className={`rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${
                  activeTab === 'history' ? 'bg-slate-950/20 text-slate-950' : 'bg-slate-800 text-slate-300'
                }`}
              >
                {sessionCount}
              </span>
            )}
          </button>
        </nav>

        <div className="flex items-center gap-2">
          {!backendOnline ? (
            <div className="flex items-center gap-2 rounded-full border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300">
              <ShieldAlert className="h-3.5 w-3.5" />
              Backend Offline (:8000)
            </div>
          ) : ollamaReady ? (
            <div className="flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{modelStatus?.model}</span>
              {modelStatus?.parameter_size && (
                <span className="text-emerald-400/80">({modelStatus.parameter_size})</span>
              )}
            </div>
          ) : ollamaReachableOnly ? (
            <div
              title={modelStatus?.hint || `Run: ollama pull ${modelStatus?.model}`}
              className="flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-300"
            >
              <Cpu className="h-3.5 w-3.5" />
              Model Missing: {modelStatus?.model}
            </div>
          ) : (
            <div
              title={modelStatus?.hint || 'Start Ollama with: ollama serve'}
              className="flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-300"
            >
              <Cpu className="h-3.5 w-3.5" />
              Ollama Offline (Diagnostics Ready)
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
