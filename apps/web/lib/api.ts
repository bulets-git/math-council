export interface Run {
  id: string;
  problem_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | string;
  config: Record<string, any>;
  budget_usd: number | string | null;
  actual_cost_usd: number | string;
  created_at: string;
  ai_notice: string;
}

export interface ProblemSummary {
  id: string;
  title: string | null;
  statement_original: string;
  input_type: string;
  subject: string | null;
  difficulty: string | null;
  created_at: string;
  latest_run_status: string | null;
}

export interface ProblemDetail {
  id: string;
  title: string | null;
  statement_original: string;
  statement_normalized: string | null;
  input_type: string;
  subject: string | null;
  difficulty: string | null;
  created_at: string;
  runs: Run[];
}

export interface CreateProblemInput {
  title?: string;
  statement_original: string;
  input_type?: 'text' | 'image' | 'mixed';
  subject?: string;
  difficulty?: string;
}

export interface CreateRunInput {
  config?: Record<string, any>;
  budget_usd?: number;
}

const getBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Client-side: use relative URL, Next.js rewrites will proxy to backend
    return '';
  }
  // Server-side (SSR / Server Component): use internal API URL
  return process.env.INTERNAL_API_URL || 'http://localhost:8000';
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Lỗi ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        errorDetail = errorJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      }
    } catch {
      // Body is not JSON
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function fetchHealth(): Promise<{ status: string; database: string }> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/health`, { cache: 'no-store' });
  return handleResponse(res);
}

export async function fetchProblems(skip = 0, limit = 100): Promise<ProblemSummary[]> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/problems?skip=${skip}&limit=${limit}`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchProblemById(id: string): Promise<ProblemDetail> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/problems/${id}`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function createProblem(data: CreateProblemInput): Promise<ProblemDetail> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/problems`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return handleResponse(res);
}

export async function createRun(problemId: string, data?: CreateRunInput): Promise<Run> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/problems/${problemId}/runs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data || {}),
  });
  return handleResponse(res);
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  context_window: number;
  is_default: boolean;
}

export interface Message {
  id: string;
  run_id: string;
  sender_role: string;
  recipient_role: string | null;
  round_number: number;
  content: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface Claim {
  id: string;
  solution_id: string;
  claim_label: string;
  content: string;
  claim_type: string | null;
  status: 'unverified' | 'supported' | 'disputed' | 'rejected' | string;
  created_at: string;
  depends_on: string[];
}

export interface SolutionDetail {
  id: string;
  run_id: string;
  solver_role: string;
  version: number;
  round_number: number;
  final_answer: string | null;
  summary: string | null;
  created_at: string;
  claims: Claim[];
}

export interface ChallengeEvent {
  id: string;
  challenge_id: string;
  actor_role: string;
  from_status: string;
  to_status: string;
  comment: string | null;
  created_at: string;
}

export interface Challenge {
  id: string;
  run_id: string;
  target_solution_id: string;
  target_claim_id: string | null;
  challenger_role: string;
  round_number: number;
  error_type: string;
  status: 'open' | 'accepted' | 'rejected' | 'unresolved' | string;
  argument: string;
  created_at: string;
  events: ChallengeEvent[];
}

export interface FinalReport {
  id: string;
  run_id: string;
  judge_role: string;
  consensus_status: string;
  winning_solution_id: string | null;
  final_latex_solution: string;
  executive_summary: string;
  dissenting_opinions: string[];
  score: number | string | null;
  created_at: string;
}

export interface ModelCall {
  id: string;
  run_id: string;
  agent_role: string;
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number | string;
  latency_ms: number;
  prompt_version: string;
  created_at: string;
}

export interface UsageSummary {
  run_id: string;
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number | string;
  calls: ModelCall[];
}

export async function fetchRunById(id: string): Promise<Run> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${id}`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function cancelRun(runId: string): Promise<Run> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/cancel`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function resumeRun(runId: string): Promise<Run> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/resume`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/models`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchRunMessages(runId: string): Promise<Message[]> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/messages`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchRunSolutions(runId: string): Promise<SolutionDetail[]> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/solutions`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchRunChallenges(runId: string): Promise<Challenge[]> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/challenges`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchRunReport(runId: string): Promise<FinalReport> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/report`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchRunUsage(runId: string): Promise<UsageSummary> {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/runs/${runId}/usage`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}
