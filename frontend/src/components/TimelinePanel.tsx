import { Clock } from 'lucide-react';
import { stateBadgeStyle } from './StatePipeline';
import type { TimelineEntry } from '../types/api';

interface TimelinePanelProps {
  timeline: TimelineEntry[];
}

export function TimelinePanel({ timeline }: TimelinePanelProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Clock className="h-4 w-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-white">Audit Timeline</h3>
      </div>

      {timeline.length === 0 ? (
        <p className="text-xs text-slate-500">No transitions recorded yet.</p>
      ) : (
        <ol className="space-y-2">
          {timeline.map((entry, idx) => {
            const timeStr = new Date(entry.at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            });
            return (
              <li
                key={`${entry.at}-${idx}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 text-xs"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${stateBadgeStyle(
                      entry.state
                    )}`}
                  >
                    {entry.state}
                  </span>
                  {entry.note && <span className="text-slate-300">{entry.note}</span>}
                </div>
                <span className="font-mono text-[11px] text-slate-500">{timeStr}</span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
