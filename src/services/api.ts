/**
 * API Service Client for Zeno Desktop AI Assistant.
 * Seamlessly interfaces with pywebview desktop bridge (window.pywebview.api)
 * or falls back to local HTTP Express backend (/api/...) and localStorage.
 */

import {
  AssistantThread,
  AgentRunRecord,
  ChecklistStep,
  WorkspaceFile,
  JobRecord,
  OrchidEvaluation,
  PendingApproval,
  SystemTelemetry,
  ApiKeySlot,
} from '../types';

declare global {
  interface Window {
    pywebview?: {
      api?: Record<string, (...args: any[]) => Promise<any>>;
    };
  }
}

async function callBridge(method: string, payload?: any): Promise<any> {
  if (typeof window !== 'undefined' && window.pywebview?.api?.[method]) {
    try {
      if (payload !== undefined) {
        return await window.pywebview.api[method](payload);
      }
      return await window.pywebview.api[method]();
    } catch (err) {
      console.error(`pywebview bridge error in ${method}:`, err);
      throw err;
    }
  }
  return null;
}

export const api = {
  // --------------------------------------------------------------------------
  // Assistant Chat & Inspection (Rule A)
  // --------------------------------------------------------------------------
  assistant: {
    async getThreads(): Promise<AssistantThread[]> {
      const bridged = await callBridge('get_assistant_threads');
      if (bridged && Array.isArray(bridged)) return bridged;

      // Fallback localStorage
      try {
        const stored = localStorage.getItem('zeno_assistant_threads');
        if (stored) return JSON.parse(stored);
      } catch {}

      // Default initial thread
      const initial: AssistantThread = {
        id: 'thread-welcome',
        title: 'Welcome to Zeno',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [
          {
            id: 'msg-welcome',
            role: 'assistant',
            content:
              'Hello! I am **Zeno**, your local Desktop AI Assistant. I can chat, explain code, answer questions, and inspect active agent runs while keeping your workspace safe.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      };
      localStorage.setItem('zeno_assistant_threads', JSON.stringify([initial]));
      return [initial];
    },

    async createThread(title: string = 'New Conversation'): Promise<AssistantThread> {
      const bridged = await callBridge('create_assistant_thread', { title });
      if (bridged && bridged.id) return bridged;

      const newThread: AssistantThread = {
        id: `thread-${Date.now()}`,
        title,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
      };
      const existing = await api.assistant.getThreads();
      const updated = [newThread, ...existing];
      localStorage.setItem('zeno_assistant_threads', JSON.stringify(updated));
      return newThread;
    },

    async deleteThread(threadId: string): Promise<boolean> {
      const bridged = await callBridge('delete_assistant_thread', { thread_id: threadId });
      if (bridged && bridged.ok !== undefined) return bridged.ok;

      const existing = await api.assistant.getThreads();
      const filtered = existing.filter((t) => t.id !== threadId);
      localStorage.setItem('zeno_assistant_threads', JSON.stringify(filtered));
      return true;
    },

    async saveThreads(threads: AssistantThread[]): Promise<void> {
      await callBridge('save_assistant_threads', { threads });
      localStorage.setItem('zeno_assistant_threads', JSON.stringify(threads));
    },

    async sendMessage(payload: {
      message: string;
      history: { role: string; content: string }[];
      model: string;
      customApiKey?: string;
      attachments?: any[];
    }): Promise<{ reply: string; inputTokens?: number; outputTokens?: number }> {
      const bridged = await callBridge('assistant_send_message', payload);
      if (bridged && bridged.reply) return bridged;

      // Fallback to Express backend /api/chat
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: payload.message,
          history: payload.history,
          model: payload.model,
          customApiKey: payload.customApiKey,
          mode: 'chat',
          attachments: payload.attachments,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.reply || err.error || `HTTP ${res.status}`);
      }
      return await res.json();
    },

    async inspectAgentRun(query: string): Promise<any> {
      const bridged = await callBridge('inspect_agent_run', { query });
      if (bridged) return bridged;

      // Fallback local search in runs
      const runs = await api.agent.getRuns();
      if (!runs || runs.length === 0) {
        return { reply: 'No agent runs exist in the workspace yet.' };
      }
      const active = runs.find((r) => r.status === 'active') || runs[0];
      return {
        reply: `Active Run: "${active.title}" [${active.status}]\nTask: ${active.task_prompt}\nProject Directory: ${active.project_folder}\nProgress: Step ${active.completed_steps} of ${active.total_steps}`,
        run: active,
      };
    },
  },

  // --------------------------------------------------------------------------
  // Agent Workspace (Rules B, C, D, E)
  // --------------------------------------------------------------------------
  agent: {
    async getRuns(): Promise<AgentRunRecord[]> {
      const bridged = await callBridge('get_agent_runs');
      if (bridged && Array.isArray(bridged)) return bridged;

      try {
        const stored = localStorage.getItem('zeno_agent_runs');
        if (stored) return JSON.parse(stored);
      } catch {}
      return [];
    },

    async createRun(payload: {
      task: string;
      projectName?: string;
      model?: string;
      customApiKey?: string;
    }): Promise<{
      run: AgentRunRecord;
      project_folder: string;
      project_name: string;
      steps: ChecklistStep[];
    }> {
      const bridged = await callBridge('create_agent_run', payload);
      if (bridged && bridged.run) return bridged;

      // Fallback offline mock for dev mode
      const folderName = (payload.projectName || payload.task.slice(0, 20).toLowerCase().replace(/[^a-z0-9]/g, '-')) || 'project-core';
      const mockRun: AgentRunRecord = {
        id: `run-${Date.now()}`,
        task_prompt: payload.task,
        title: folderName,
        workspace_name: folderName,
        project_folder: `~/Documents/ZenoWorkspace/${folderName}`,
        status: 'queued',
        current_step_id: 'step_1',
        completed_steps: 0,
        total_steps: 5,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const mockSteps: ChecklistStep[] = [
        {
          id: 'step_1',
          title: 'Scaffold project architecture and requirements',
          status: 'pending',
          depends_on: [],
          retry_count: 0,
          max_retries: 3,
          evidence: { files_created: [], command_exit_codes: [] },
        },
        {
          id: 'step_2',
          title: 'Implement core modules and business logic',
          status: 'pending',
          depends_on: ['step_1'],
          retry_count: 0,
          max_retries: 3,
          evidence: { files_created: [], command_exit_codes: [] },
        },
        {
          id: 'step_3',
          title: 'Author automated unit and boundary tests',
          status: 'pending',
          depends_on: ['step_2'],
          retry_count: 0,
          max_retries: 3,
          evidence: { files_created: [], command_exit_codes: [] },
        },
        {
          id: 'step_4',
          title: 'Execute test suite and verify passing exit code',
          status: 'pending',
          depends_on: ['step_3'],
          retry_count: 0,
          max_retries: 3,
          evidence: { files_created: [], command_exit_codes: [] },
        },
        {
          id: 'step_5',
          title: 'Finalize documentation and executive summary',
          status: 'pending',
          depends_on: ['step_4'],
          retry_count: 0,
          max_retries: 3,
          evidence: { files_created: [], command_exit_codes: [] },
        },
      ];

      const existing = await api.agent.getRuns();
      localStorage.setItem('zeno_agent_runs', JSON.stringify([mockRun, ...existing]));
      return {
        run: mockRun,
        project_folder: mockRun.project_folder,
        project_name: folderName,
        steps: mockSteps,
      };
    },

    async getRunChecklist(projectFolder: string): Promise<{
      steps: ChecklistStep[];
      progress: any;
      jumps: any[];
    }> {
      const bridged = await callBridge('get_run_checklist', { project_folder: projectFolder });
      if (bridged && Array.isArray(bridged.steps)) return bridged;
      return { steps: [], progress: {}, jumps: [] };
    },

    async executeStep(payload: {
      run_id: string;
      step_id?: string;
      project_folder: string;
      model?: string;
      customApiKey?: string;
      history?: any[];
    }): Promise<any> {
      const bridged = await callBridge('execute_agent_step', payload);
      if (bridged) return bridged;

      // Fallback dev response
      return {
        step_id: payload.step_id || 'step_1',
        step_status: 'completed',
        reply: 'Simulated step execution completed in development mode.',
        exit_code: 0,
        files_created: ['main.py', 'test_main.py'],
        orchid_verdict: { verdict: 'ALLOW', rule: 'rule_allow_project_file_write', reason: 'Safe project write' },
      };
    },

    async jumpToStep(payload: {
      project_folder: string;
      target_step_id: string;
      reason: string;
    }): Promise<{ ok: boolean; message: string }> {
      const bridged = await callBridge('jump_to_step', payload);
      if (bridged) return bridged;
      return { ok: true, message: `Jumped to step ${payload.target_step_id}` };
    },

    async renameProjectFolder(payload: {
      run_id: string;
      new_name: string;
    }): Promise<{ ok: boolean; new_name?: string; error?: string }> {
      const bridged = await callBridge('rename_project_folder', payload);
      if (bridged) return bridged;
      return { ok: true, new_name: payload.new_name };
    },

    async stopRun(runId: string): Promise<boolean> {
      const bridged = await callBridge('stop_agent_run', { run_id: runId });
      if (bridged) return true;
      return true;
    },
  },

  // --------------------------------------------------------------------------
  // Workspace Files (Rule B)
  // --------------------------------------------------------------------------
  files: {
    async listFiles(projectFolder?: string): Promise<WorkspaceFile[]> {
      const bridged = await callBridge('list_project_files', { project_folder: projectFolder });
      if (bridged && Array.isArray(bridged)) return bridged;
      return [];
    },

    async readFileBase64(filePath: string): Promise<{
      ok: boolean;
      name?: string;
      mime_type?: string;
      text?: string;
      base64?: string;
      error?: string;
    }> {
      const bridged = await callBridge('read_file_for_viewer', { path: filePath });
      if (bridged) return bridged;
      return { ok: false, error: 'Bridge not available' };
    },

    async revealInExplorer(filePath: string): Promise<boolean> {
      const bridged = await callBridge('open_in_explorer', { path: filePath });
      if (bridged) return true;
      return false;
    },
  },

  // --------------------------------------------------------------------------
  // Job Process Supervisor (Rule E & G)
  // --------------------------------------------------------------------------
  jobs: {
    async listJobs(): Promise<JobRecord[]> {
      const bridged = await callBridge('list_background_jobs');
      if (bridged && Array.isArray(bridged)) return bridged;
      return [];
    },

    async stopJob(jobId: string): Promise<boolean> {
      const bridged = await callBridge('cancel_background_job', { job_id: jobId });
      if (bridged) return true;
      return false;
    },

    async getJobLogs(jobId: string, lines: number = 200): Promise<{ logs: string[] }> {
      const bridged = await callBridge('get_job_logs', { job_id: jobId, lines });
      if (bridged && bridged.logs) return bridged;
      return { logs: [] };
    },
  },

  // --------------------------------------------------------------------------
  // Orchid Security Kernel (Rule F)
  // --------------------------------------------------------------------------
  orchid: {
    async listEvaluations(limit: number = 50): Promise<OrchidEvaluation[]> {
      const bridged = await callBridge('get_safety_evaluations', { limit });
      if (bridged && Array.isArray(bridged)) return bridged;

      // Fallback
      return [
        {
          verdict: 'ALLOW',
          rule_name: 'rule_allow_venv_dependency_install',
          reason: 'Package installation into project isolated virtual environment (.venv) is safe and permitted.',
          action_type: 'shell_run',
          action_target: '.venv/Scripts/pip install django',
          timestamp: new Date().toLocaleTimeString(),
        },
        {
          verdict: 'ALLOW',
          rule_name: 'rule_allow_project_file_write',
          reason: 'File write is contained strictly inside project folder.',
          action_type: 'write_file',
          action_target: 'manage.py',
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    },

    async listPendingApprovals(): Promise<PendingApproval[]> {
      const bridged = await callBridge('list_pending_approvals');
      if (bridged && Array.isArray(bridged)) return bridged;
      return [];
    },

    async decideApproval(approvalId: string, decision: 'APPROVE' | 'DENY'): Promise<boolean> {
      const bridged = await callBridge('decide_approval', {
        approval_id: approvalId,
        decision,
      });
      if (bridged) return true;
      return true;
    },
  },

  // --------------------------------------------------------------------------
  // Memory & System Telemetry
  // --------------------------------------------------------------------------
  memory: {
    async getMemory(): Promise<string> {
      const bridged = await callBridge('get_user_memory');
      if (bridged && bridged.memory !== undefined) return bridged.memory;

      const res = await fetch('/api/memory').catch(() => null);
      if (res && res.ok) {
        const data = await res.json();
        return data.memory || '';
      }
      return '';
    },

    async saveMemory(content: string): Promise<boolean> {
      const bridged = await callBridge('save_user_memory', { content });
      if (bridged) return true;

      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      }).catch(() => null);
      return res ? res.ok : true;
    },

    async synthesize(notes: string, customApiKey?: string, model?: string): Promise<string> {
      const bridged = await callBridge('synthesize_memory', { notes, customApiKey, model });
      if (bridged && bridged.memory) return bridged.memory;

      const res = await fetch('/api/memory/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes, customApiKey, model }),
      }).catch(() => null);
      if (res && res.ok) {
        const data = await res.json();
        return data.memory || '';
      }
      return notes;
    },
  },

  // --------------------------------------------------------------------------
  // Settings & System Status
  // --------------------------------------------------------------------------
  settings: {
    async getSystemStatus(): Promise<SystemTelemetry | null> {
      const bridged = await callBridge('get_system_status');
      if (bridged && bridged.os_name) return bridged;

      const res = await fetch('/api/system-status').catch(() => null);
      if (res && res.ok) {
        return await res.json();
      }
      return null;
    },

    async getPermissions(): Promise<Record<string, boolean>> {
      const bridged = await callBridge('get_permissions');
      if (bridged && typeof bridged === 'object') return bridged;
      try {
        const saved = localStorage.getItem('zeno_permissions');
        if (saved) return JSON.parse(saved);
      } catch {}
      return {
        file_read: true,
        file_write: true,
        python_exec: true,
        web_search: true,
        screen_capture: false,
        clipboard: false,
        app_launch: false,
        dev_tools: true,
      };
    },

    async savePermissions(permissions: Record<string, boolean>): Promise<boolean> {
      const bridged = await callBridge('save_all_permissions', { permissions });
      localStorage.setItem('zeno_permissions', JSON.stringify(permissions));
      if (bridged) return true;
      return true;
    },
  },

  // Delete methods across tabs
  delete: {
    async files(payload: { paths?: string[]; all?: boolean; projectFolder?: string }): Promise<boolean> {
      const bridged = await callBridge('delete_workspace_files', payload);
      if (bridged) return bridged.ok;
      return true;
    },

    async jobs(jobIds?: string[]): Promise<boolean> {
      const bridged = await callBridge('clear_background_jobs', { job_ids: jobIds });
      if (bridged) return true;
      return true;
    },

    async orchidLogs(logIds?: (number | string)[]): Promise<boolean> {
      const bridged = await callBridge('clear_safety_evaluations', { log_ids: logIds });
      if (bridged) return bridged.ok;
      return true;
    },
  },
};
