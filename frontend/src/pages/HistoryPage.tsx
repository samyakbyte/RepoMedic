import { ArrowUpRight, Download, History } from 'lucide-react';
import { api } from '../lib/api';
import { stateBadgeStyle } from '../components/StatePipeline';
import type { SessionSummary } from '../types/api';

interface HistoryPageProps {
  sessions: SessionSummary[];
  onOpenSession: (sessionId: string) => void;
}

export function HistoryPage({ sessions, onOpenSession }: HistoryPageProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-white">
            <History className="h-5 w-5 text-emerald-400" />
            Repair Sessions History
          </h2>
          <p className="text-xs text-slate-400">
            Persisted on disk under <code className="text-slate-300">data/sessions/</code> across restarts.
          </p>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-8 text-center text-xs text-slate-400">
          No repair sessions recorded yet. Start one from the Repair Studio tab!
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/80 uppercase text-slate-400">
              <tr>
                <th className="px-3.5 py-2.5">Session ID</th>
                <th className="px-3.5 py-2.5">Project</th>
                <th className="px-3.5 py-2.5">State</th>
                <th className="px-3.5 py-2.5">Attempts</th>
                <th className="px-3.5 py-2.5">Verdict</th>
                <th className="px-3.5 py-2.5">Updated</th>
                <th className="px-3.5 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/40">
              {sessions.map((s) => (
                <tr key={s.id} className="hover:bg-slate-800/40">
                  <td className="px-3.5 py-2.5 font-mono text-emerald-300">{s.id}</td>
                  <td className="px-3.5 py-2.5 font-medium text-white">{s.project_id}</td>
                  <td className="px-3.5 py-2.5">
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${stateBadgeStyle(
                        s.state
                      )}`}
                    >
                      {s.state}
                    </span>
                  </td>
                  <td className="px-3.5 py-2.5 text-slate-300">
                    {s.attempt} / {s.max_attempts}
                  </td>
                  <td className="px-3.5 py-2.5 font-mono text-slate-300">{s.verdict || '—'}</td>
                  <td className="px-3.5 py-2.5 text-slate-400">
                    {new Date(s.updated_at).toLocaleString()}
                  </td>
                  <td className="px-3.5 py-2.5 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => onOpenSession(s.id)}
                        className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/15 px-2.5 py-1 font-medium text-emerald-300 hover:bg-emerald-500/25"
                      >
                        Open <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                      <a
                        href={api.reportDownloadUrl(s.id, 'md')}
                        download={`${s.id}.md`}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-300 hover:bg-slate-700"
                      >
                        <Download className="h-3 w-3" /> MD
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
