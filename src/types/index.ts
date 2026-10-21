/**
 * Unified Type Definitions for Zeno Desktop AI Assistant
 */

export type NavigationTab =
  | 'assistant'
  | 'agent'
  | 'files'
  | 'jobs'
  | 'orchid'
  | 'memory'
  | 'settings';

export interface AttachedItem {
  id: string;
  name: string;
  type: string;
  size: string;
  base64?: string;
  content?: string;
}

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  attachments?: AttachedItem[];
  tokens?: { input: number; output: number };
  isStreaming?: boolean;
}

export interface AssistantThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: AssistantMessage[];
}

export type StepStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'skipped';

export interface OrchidVerdictRecord {
  verdict: 'ALLOW' | 'DENY' | 'ASK_USER';
  rule: string;
  reason: string;
}

export interface StepEvidence {
  files_created: string[];
  command_exit_codes: number[];
  test_results?: string;
  screenshot_path?: string;
}

export interface ChecklistStep {
  id: string;
  title: string;
  status: StepStatus;
  depends_on: string[];
  retry_count: number;
  max_retries: number;
  evidence: StepEvidence;
  orchid_verdict?: OrchidVerdictRecord;
  error_message?: string;
  updated_at?: string;
}

export interface HistoryJump {
  from_step: string;
  to_step: string;
  reason: string;
  timestamp: string;
}

export type AgentRunStatus =
  | 'queued'
  | 'active'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'aborted';

export interface AgentRunRecord {
  id: string;
  task_prompt: string;
  title: string;
  workspace_name: string;
  project_folder: string;
  status: AgentRunStatus;
  current_step_id: string;
  completed_steps: number;
  total_steps: number;
  created_at: string;
  updated_at: string;
  last_error?: string;
  summary?: string;
}

export interface WorkspaceFile {
  name: string;
  path: string;
  mime_type: string;
  size: string;
  size_bytes?: number;
  modified_at?: string;
}

export interface JobRecord {
  job_id: string;
  command: string;
  pid: number;
  cwd: string;
  started_at: string;
  status: 'running' | 'completed' | 'failed' | 'terminated';
  exit_code?: number;
  log_snippet?: string;
}

export interface OrchidEvaluation {
  verdict: 'ALLOW' | 'DENY' | 'ASK_USER';
  rule_name: string;
  reason: string;
  action_type: string;
  action_target: string;
  timestamp: string;
}

export interface PendingApproval {
  id: string;
  tool_name: string;
  rule_name: string;
  reason: string;
  payload: any;
  created_at: string;
}

export interface ApiKeySlot {
  id: string;
  provider: 'Gemini' | 'Anthropic Claude' | 'OpenRouter' | 'OpenAI' | 'Groq';
  key: string;
}

export interface SystemTelemetry {
  os_name: string;
  os_version: string;
  python_version: string;
  battery: string;
  cpu_percent: number;
  cpu_model: string;
  ram_used_gb: number;
  ram_total_gb: number;
  ram_percent: number;
  disk_free_gb: number;
  disk_total_gb: number;
  uptime: string;
  timestamp: string;
}
