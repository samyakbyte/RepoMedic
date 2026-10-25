import { useCallback, useEffect, useState } from 'react';
import { Play, Loader2, CheckCircle2, XCircle, BarChart3 } from 'lucide-react';
import { api, RepoMedicApiError } from '../lib/api';
import type { BenchmarkJobDetail, BenchmarkJobSummary, Project } from '../types/api';

interface BenchmarksPageProps {
  projects: Project[];
}

export function BenchmarksPage({ projects }: BenchmarksPageProps) {
  const [runsPerProject, setRunsPerProject] = useState(1);
  const [jobs, setJobs] = useState<BenchmarkJobSummary[]>([]);
  const [selectedJob, setSelectedJob] = useState<BenchmarkJobDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const list = await api.listBenchmarks();
      setJobs(list);
      if (list.length > 0 && !selectedJob) {
        const detail = await api.getBenchmark(list[0].job_id);
        setSelectedJob(detail);
      }
    } catch {
      // ignore initial error
    }
  }, [selectedJob]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (!selectedJob || selectedJob.status !== 'running') return;
    const timer = window.setInterval(async () => {
      try {
        const detail = await api.getBenchmark(selectedJob.job_id);
        setSelectedJob(detail);
        if (detail.status !== 'running') {
          setJobs(await api.listBenchmarks());
        }
      } catch {
        // ignore transient poll errors
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [selectedJob]);

  const handleStart = async () => {
    setError(null);
    setStarting(true);
    try {
      const started = await api.startBenchmark({
        runs_per_project: runsPerProject,
        project_ids: projects.map((p) => p.id),
      });
      const detail = await api.getBenchmark(started.job_id);
      setSelectedJob(detail);
      setJobs(await api.listBenchmarks());
    } catch (err) {
      setError(err instanceof RepoMedicApiError ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-white">
            <BarChart3 className="h-5 w-5 text-emerald-400" />
            Automated Repair Benchmarks
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Runs diagnose → generate → validate → apply → verify across all {projects.length} demo projects in clean temporary sandboxes and writes results to <code className="text-slate-300">benchmarks/results/</code>.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300">
            Runs / project:
            <select
              value={runsPerProject}
              onChange={(e) => setRunsPerProject(Number(e.target.value))}
              className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white"
            >
              {[1, 2, 3, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={starting || selectedJob?.status === 'running'}
            onClick={handleStart}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
          >
            {starting || selectedJob?.status === 'running' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running Sweep...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Benchmark Sweep
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-200">
          {error}
        </div>
      )}

      {jobs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {jobs.map((j) => (
            <button
              key={j.job_id}
              type="button"
              onClick={async () => setSelectedJob(await api.getBenchmark(j.job_id))}
              className={`rounded-xl border px-3 py-1.5 text-xs font-mono transition ${
                selectedJob?.job_id === j.job_id
                  ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-200'
                  : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              {j.job_id} ({j.status})
            </button>
          ))}
        </div>
      )}

      {selectedJob && (
        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">Success Rate</div>
              <div className="mt-1 text-2xl font-bold text-emerald-400">
                {selectedJob.summary?.success_rate != null
                  ? `${(selectedJob.summary.success_rate * 100).toFixed(0)}%`
                  : '—'}
              </div>
              <div className="text-xs text-slate-400">
                {selectedJob.summary?.verified_runs ?? 0} / {selectedJob.summary?.total_runs ?? 0} verified
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">
                First-Attempt Rate
              </div>
              <div className="mt-1 text-2xl font-bold text-sky-400">
                {selectedJob.summary?.first_attempt_success_rate != null
                  ? `${(selectedJob.summary.first_attempt_success_rate * 100).toFixed(0)}%`
                  : '—'}
              </div>
              <div className="text-xs text-slate-400">Model: {selectedJob.model}</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">
                Mean Gen Latency
              </div>
              <div className="mt-1 text-2xl font-bold text-white">
                {selectedJob.summary?.mean_generation_time_s != null
                  ? `${selectedJob.summary.mean_generation_time_s}s`
                  : '—'}
              </div>
              <div className="text-xs text-slate-400">
                Median: {selectedJob.summary?.median_generation_time_s ?? '—'}s
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">Throughput</div>
              <div className="mt-1 text-2xl font-bold text-amber-300">
                {selectedJob.summary?.mean_tokens_per_second != null
                  ? `${selectedJob.summary.mean_tokens_per_second} tok/s`
                  : '—'}
              </div>
              <div className="truncate text-xs text-slate-400" title={selectedJob.summary?.hardware}>
                {selectedJob.summary?.hardware || 'Local runtime'}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-slate-950/80 uppercase text-slate-400">
                <tr>
                  <th className="px-3 py-2.5">Project</th>
                  <th className="px-3 py-2.5">Run</th>
                  <th className="px-3 py-2.5">Outcome</th>
                  <th className="px-3 py-2.5">Attempts</th>
                  <th className="px-3 py-2.5">Tests (Before → After)</th>
                  <th className="px-3 py-2.5">Gen Time</th>
                  <th className="px-3 py-2.5">Tok/s</th>
                  <th className="px-3 py-2.5">Notes / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-900/40">
                {selectedJob.results.map((r, idx) => (
                  <tr key={`${r.project}-${r.run}-${idx}`}>
                    <td className="px-3 py-2 font-mono font-medium text-white">{r.project}</td>
                    <td className="px-3 py-2 text-slate-300">#{r.run}</td>
                    <td className="px-3 py-2">
                      {r.outcome === 'VERIFIED' ? (
                        <span className="inline-flex items-center gap-1 text-emerald-300">
                          <CheckCircle2 className="h-3.5 w-3.5" /> VERIFIED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-300">
                          <XCircle className="h-3.5 w-3.5" /> {r.outcome}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-300">{r.attempts_used}</td>
                    <td className="px-3 py-2 font-mono text-slate-300">
                      {r.initial_passed}P/{r.initial_failed}F → {r.final_passed}P/{r.final_failed}F
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-300">
                      {r.generation_time_s != null ? `${r.generation_time_s.toFixed(2)}s` : '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-300">
                      {r.tokens_per_second != null ? r.tokens_per_second.toFixed(1) : '—'}
                    </td>
                    <td className="max-w-xs truncate px-3 py-2 text-slate-400" title={r.error || ''}>
                      {r.error || (r.validation_codes.length ? r.validation_codes.join(', ') : '—')}
                    </td>
                  </tr>
                ))}
                {selectedJob.results.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3 py-6 text-center text-slate-400">
                      Benchmark in progress — results will populate once runs complete.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
