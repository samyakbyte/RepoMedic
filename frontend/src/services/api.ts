import type {
  ApiErrorBody,
  BenchmarkJobDetail,
  BenchmarkJobSummary,
  ModelStatus,
  Project,
  SessionDetail,
  SessionFilesResponse,
  SessionSummary,
} from '../types/api';

export class RepoMedicApiError extends Error {
  code: string;
  hint?: string | null;
  state?: string | null;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'RepoMedicApiError';
    this.status = status;
    this.code = body.code;
    this.hint = body.hint;
    this.state = body.state;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let errBody: ApiErrorBody = {
      code: `HTTP_${res.status}`,
      message: `Request failed with status ${res.status}`,
    };
    try {
      const json = await res.json();
      if (json?.error?.message) {
        errBody = json.error;
      } else if (json?.detail) {
        errBody = {
          code: `HTTP_${res.status}`,
          message: typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail),
        };
      }
    } catch {
      // ignore non-json error body
    }
    throw new RepoMedicApiError(res.status, errBody);
  }

  return (await res.json()) as T;
}

export const api = {
  getHealth: () => request<{ status: string; version: string }>('/api/health'),
  getModelStatus: () => request<ModelStatus>('/api/model/status'),
  listProjects: () => request<Project[]>('/api/projects'),

  listSessions: () => request<SessionSummary[]>('/api/sessions'),
  createSession: (project_id: string) =>
    request<SessionSummary>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({ project_id }),
    }),
  getSession: (sessionId: string) => request<SessionDetail>(`/api/sessions/${sessionId}`),
  getSessionFiles: (sessionId: string) =>
    request<SessionFilesResponse>(`/api/sessions/${sessionId}/files`),

  diagnoseSession: (sessionId: string) =>
    request<{ session_id: string; state: string }>(`/api/sessions/${sessionId}/diagnose`, {
      method: 'POST',
    }),
  repairSession: (sessionId: string) =>
    request<{ session_id: string; state: string; attempt: number }>(
      `/api/sessions/${sessionId}/repair`,
      { method: 'POST' }
    ),
  approvePatch: (sessionId: string) =>
    request<{ session_id: string; state: string; attempt: number }>(
      `/api/sessions/${sessionId}/approve`,
      { method: 'POST' }
    ),
  rejectPatch: (sessionId: string, reason?: string) =>
    request<{ session_id: string; state: string; attempt: number }>(
      `/api/sessions/${sessionId}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({ reason: reason || 'Rejected by reviewer in UI' }),
      }
    ),
  rollbackPatch: (sessionId: string) =>
    request<{ session_id: string; state: string; restored_sha: string }>(
      `/api/sessions/${sessionId}/rollback`,
      { method: 'POST' }
    ),
  resetSession: (sessionId: string) =>
    request<SessionSummary>(`/api/sessions/${sessionId}/reset`, { method: 'POST' }),

  reportDownloadUrl: (sessionId: string, format: 'json' | 'md') =>
    `/api/sessions/${sessionId}/report?format=${format}`,

  listBenchmarks: () => request<BenchmarkJobSummary[]>('/api/benchmarks'),
  getBenchmark: (jobId: string) => request<BenchmarkJobDetail>(`/api/benchmarks/${jobId}`),
  startBenchmark: (params: { runs_per_project: number; project_ids?: string[] }) =>
    request<{ job_id: string; status: string; model: string; runs_per_project: number }>(
      '/api/benchmarks/run',
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    ),
};
