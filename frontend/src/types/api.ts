export type SessionState =
  | 'IDLE'
  | 'DIAGNOSING'
  | 'FAILURE_DETECTED'
  | 'GENERATING_REPAIR'
  | 'PATCH_READY'
  | 'AWAITING_APPROVAL'
  | 'APPLYING_PATCH'
  | 'VERIFYING'
  | 'REPAIR_VERIFIED'
  | 'REPAIR_FAILED'
  | 'ERROR';

export const WORKING_STATES: ReadonlySet<SessionState> = new Set<SessionState>([
  'DIAGNOSING',
  'GENERATING_REPAIR',
  'APPLYING_PATCH',
  'VERIFYING',
]);

export interface Project {
  id: string;
  name: string;
  description: string;
  bug_category: string;
  failing_test: string;
  test_command: string[];
  target_files: string[];
}

export interface ModelStatus {
  ollama_reachable: boolean;
  model_available: boolean;
  model: string;
  parameter_size?: string | null;
  quantization?: string | null;
  family?: string | null;
  hint?: string | null;
}

export interface Failure {
  test_id: string;
  file?: string | null;
  line?: number | null;
  message: string;
  traceback?: string | null;
}

export interface DiagnosticsResult {
  exit_code: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  total: number;
  duration_s: number;
  failures: Failure[];
  passing_tests: string[];
  raw_output: string;
  timeout_occurred: boolean;
  error_type?: string | null;
}

export interface RepairProposal {
  root_cause: string;
  target_file: string;
  old_snippet: string;
  new_snippet: string;
  explanation: string;
  expected_outcome: string;
}

export interface PatchValidationResult {
  ok: boolean;
  codes: string[];
  snippet_normalized: boolean;
  diff?: string | null;
  before: string;
  after: string;
  old_snippet_found_at?: number | null;
}

export interface LLMMetrics {
  model: string;
  duration_s: number;
  prompt_eval_count?: number | null;
  eval_count?: number | null;
  eval_duration_ns?: number | null;
  total_duration_ns?: number | null;
  load_duration_ns?: number | null;
  tokens_per_second?: number | null;
}

export interface VerificationResult {
  verdict: 'REPAIR_VERIFIED' | 'REPAIR_FAILED' | string;
  reason?: string | null;
  passed: number;
  failed: number;
  errors: number;
  total: number;
  duration_s: number;
  originally_failing_now_passing: string[];
  regressions: string[];
  timeout_occurred: boolean;
  raw_output: string;
}

export interface AttemptRecord {
  n: number;
  patch: RepairProposal;
  validation: PatchValidationResult;
  llm: LLMMetrics;
  approved?: boolean | null;
  rejected_reason?: string | null;
  verification?: VerificationResult | null;
}

export interface TimelineEntry {
  state: SessionState;
  at: string;
  note?: string | null;
}

export interface SessionSummary {
  id: string;
  project_id: string;
  state: SessionState;
  attempt: number;
  max_attempts: number;
  verdict?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionSummary {
  project_name?: string | null;
  diagnostics_before?: DiagnosticsResult | null;
  attempts: AttemptRecord[];
  timeline: TimelineEntry[];
  report_path?: string | null;
}

export interface SessionFilesResponse {
  session_id: string;
  project_id: string;
  files: Record<string, string>;
}

export interface BenchmarkSummary {
  model?: string;
  total_runs?: number;
  verified_runs?: number;
  success_rate?: number;
  first_attempt_success_rate?: number;
  mean_generation_time_s?: number | null;
  median_generation_time_s?: number | null;
  mean_tokens_per_second?: number | null;
  hardware?: string;
  error?: string;
}

export interface BenchmarkRunRecord {
  project: string;
  bug_category: string;
  model: string;
  run: number;
  attempt: number;
  initial_failed: number;
  initial_passed: number;
  final_passed: number;
  final_failed: number;
  original_failure_resolved: boolean;
  regressions: boolean;
  patch_validation_ok: boolean;
  validation_codes: string[];
  attempts_used: number;
  generation_time_s?: number | null;
  verification_time_s?: number | null;
  total_time_s?: number | null;
  tokens_per_second?: number | null;
  outcome: string;
  error?: string | null;
}

export interface BenchmarkJobSummary {
  job_id: string;
  model: string;
  runs_per_project?: number;
  status: 'running' | 'done' | 'failed' | string;
  created_at: string;
  finished_at?: string | null;
  runs: number;
  summary: BenchmarkSummary;
}

export interface BenchmarkJobDetail extends BenchmarkJobSummary {
  results: BenchmarkRunRecord[];
}

export interface ApiErrorBody {
  code: string;
  message: string;
  hint?: string | null;
  state?: string | null;
}
