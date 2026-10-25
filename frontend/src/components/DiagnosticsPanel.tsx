import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, Terminal, XCircle, CheckCircle2 } from 'lucide-react';
import type { DiagnosticsResult } from '../types/api';

interface DiagnosticsPanelProps {
  diagnostics: DiagnosticsResult;
  files: Record<string, string>;
}

export function DiagnosticsPanel({ diagnostics, files }: DiagnosticsPanelProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(
    Object.keys(files)[0] ?? null
  );

  const fileKeys = Object.keys(files);
  const currentFile = selectedFile && files[selectedFile] ? selectedFile : fileKeys[0] ?? null;

  return (
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Pytest Diagnostics (Pre-Repair)</h3>
          <p className="text-xs text-slate-400">
            Executed inside isolated workspace via JUnit XML parser in {diagnostics.duration_s.toFixed(2)}s
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold">
          <span className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {diagnostics.passed} Passed
          </span>
          <span className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-rose-300">
            <XCircle className="h-3.5 w-3.5" />
            {diagnostics.failed} Failed
          </span>
          {diagnostics.errors > 0 && (
            <span className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-rose-300">
              {diagnostics.errors} Errors
            </span>
          )}
        </div>
      </div>

      {diagnostics.failures.length > 0 && (
        <div className="space-y-2.5">
          {diagnostics.failures.map((f) => (
            <div
              key={f.test_id}
              className="rounded-xl border border-rose-500/30 bg-slate-950/80 p-3.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold text-rose-300">{f.test_id}</span>
                {f.line != null && (
                  <span className="font-mono text-[11px] text-slate-400">
                    {f.file}:{f.line}
                  </span>
                )}
              </div>
              <p className="mt-1.5 font-mono text-xs text-amber-200">{f.message}</p>
              {f.traceback && (
                <pre className="mt-2 max-h-44 overflow-auto rounded-lg bg-slate-900 p-2.5 font-mono text-[11px] leading-relaxed text-slate-300">
                  {f.traceback.trim()}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {fileKeys.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-950/70">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
              <FileText className="h-3.5 w-3.5 text-emerald-400" />
              Workspace Inspector
            </div>
            <div className="flex flex-wrap gap-1">
              {fileKeys.map((fk) => (
                <button
                  key={fk}
                  type="button"
                  onClick={() => setSelectedFile(fk)}
                  className={`rounded-md px-2.5 py-1 font-mono text-[11px] transition ${
                    currentFile === fk
                      ? 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40'
                      : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {fk}
                </button>
              ))}
            </div>
          </div>
          {currentFile && (
            <pre className="max-h-64 overflow-auto p-3 font-mono text-xs leading-relaxed text-slate-200">
              {files[currentFile]
                .split('\n')
                .map((line, idx) => `${String(idx + 1).padStart(3, ' ')} │ ${line}`)
                .join('\n')}
            </pre>
          )}
        </div>
      )}

      <div>
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-200"
        >
          {showRaw ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          <Terminal className="h-3.5 w-3.5" />
          {showRaw ? 'Hide Raw Pytest Output' : 'Show Raw Pytest Output'}
        </button>
        {showRaw && (
          <pre className="mt-2 max-h-56 overflow-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] text-slate-300">
            {diagnostics.raw_output}
          </pre>
        )}
      </div>
    </div>
  );
}
