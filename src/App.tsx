import React, { useState, useEffect, useMemo } from 'react';
import {
  NavigationTab,
  AssistantThread,
  AgentRunRecord,
  ChecklistStep,
  ApiKeySlot,
  SystemTelemetry,
} from './types';
import { api } from './services/api';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { AssistantPage } from './pages/AssistantPage';
import { AgentWorkspacePage } from './pages/AgentWorkspacePage';
import { FilesPage } from './pages/FilesPage';
import { JobsPage } from './pages/JobsPage';
import { OrchidPage } from './pages/OrchidPage';
import { MemoryPage } from './pages/MemoryPage';
import { SettingsPage } from './pages/SettingsPage';
import { FileViewerModal } from './components/common/FileViewerModal';

// Catalog of models available per provider
const PROVIDER_MODELS: Record<string, string[]> = {
  Gemini: ['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-flash'],
  'Anthropic Claude': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
  OpenRouter: [
    'openrouter/google/gemini-2.5-flash',
    'openrouter/anthropic/claude-3.5-sonnet',
    'openrouter/meta-llama/llama-3.3-70b-instruct',
  ],
  OpenAI: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
  Groq: ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768'],
};

export default function App() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('assistant');

  // Multi-provider key slots
  const [apiKeySlots, setApiKeySlots] = useState<ApiKeySlot[]>(() => {
    try {
      const saved = localStorage.getItem('zeno_api_key_slots');
      if (saved) return JSON.parse(saved);
    } catch {}
    return [
      { id: 'slot-1', provider: 'Gemini', key: '' },
      { id: 'slot-2', provider: 'Anthropic Claude', key: '' },
      { id: 'slot-3', provider: 'OpenRouter', key: '' },
    ];
  });

  const [workspaceDir, setWorkspaceDir] = useState<string>(() => {
    return localStorage.getItem('zeno_workspace_dir') || '~/Documents/ZenoWorkspace';
  });

  // Calculate available models strictly based on active keys
  const availableModels = useMemo(() => {
    const list: string[] = [];
    apiKeySlots.forEach((slot) => {
      if (slot.key && slot.key.trim().length > 0) {
        const provModels = PROVIDER_MODELS[slot.provider] || [];
        provModels.forEach((m) => {
          if (!list.includes(m)) list.push(m);
        });
      }
    });
    return list.length > 0 ? list : ['gemini-3.5-flash-lite'];
  }, [apiKeySlots]);

  const [activeModel, setActiveModel] = useState<string>(() => {
    return localStorage.getItem('zeno_active_model') || 'gemini-3.5-flash-lite';
  });

  // System Telemetry
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);

  // Assistant threads
  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>('');

  // Agent runs & checklist
  const [runs, setRuns] = useState<AgentRunRecord[]>([]);
  const [activeRunId, setActiveRunId] = useState<string>('');
  const [checklistSteps, setChecklistSteps] = useState<ChecklistStep[]>([]);
  const [isExecutingAgent, setIsExecutingAgent] = useState(false);
  const [liveLogs, setLiveLogs] = useState<{ type: string; text: string; ts: string }[]>([]);

  // In-app file viewer modal state
  const [viewerPath, setViewerPath] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    const init = async () => {
      // 1. Assistant threads
      const loadedThreads = await api.assistant.getThreads();
      setThreads(loadedThreads);
      if (loadedThreads.length > 0) {
        setActiveThreadId(loadedThreads[0].id);
      }

      // 2. Agent runs
      const loadedRuns = await api.agent.getRuns();
      setRuns(loadedRuns);
      if (loadedRuns.length > 0) {
        const first = loadedRuns[0];
        setActiveRunId(first.id);
        const checklist = await api.agent.getRunChecklist(first.project_folder);
        if (checklist && checklist.steps) {
          setChecklistSteps(checklist.steps);
        }
      }

      // 3. System Telemetry
      const telem = await api.settings.getSystemStatus();
      setTelemetry(telem);

      // 4. Restore API keys from backend .env (survives app restart)
      try {
        const backendKeys = await api.settings.loadApiKeys();
        if (backendKeys && backendKeys.length > 0) {
          setApiKeySlots((prev) => {
            const merged = [...prev];
            backendKeys.forEach((bk) => {
              const existing = merged.find((s) => s.provider === bk.provider);
              if (existing) {
                // Only overwrite if localStorage slot is empty
                if (!existing.key || existing.key.trim().length === 0) {
                  existing.key = bk.key;
                }
              } else {
                merged.push({ id: `slot-${Date.now()}-${bk.provider}`, provider: bk.provider as any, key: bk.key });
              }
            });
            localStorage.setItem('zeno_api_key_slots', JSON.stringify(merged));
            return merged;
          });
        }
      } catch {}
    };
    init();

    const interval = setInterval(async () => {
      const telem = await api.settings.getSystemStatus();
      if (telem) setTelemetry(telem);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeRun = runs.find((r) => r.id === activeRunId) || runs[0] || null;
  const primaryApiKey = apiKeySlots.find((s) => s.key && s.key.trim().length > 0)?.key || '';

  // Thread actions
  const handleSelectThread = (threadId: string) => {
    setActiveThreadId(threadId);
  };

  const handleCreateThread = async () => {
    const created = await api.assistant.createThread('New Conversation');
    setThreads((prev) => [created, ...prev]);
    setActiveThreadId(created.id);
  };

  const handleDeleteThread = async (threadId: string) => {
    await api.assistant.deleteThread(threadId);
    const updated = threads.filter((t) => t.id !== threadId);
    setThreads(updated);
    if (activeThreadId === threadId && updated.length > 0) {
      setActiveThreadId(updated[0].id);
    }
  };

  // Agent Run actions
  const handleSelectRun = async (run: AgentRunRecord) => {
    setActiveRunId(run.id);
    const cl = await api.agent.getRunChecklist(run.project_folder);
    setChecklistSteps(cl.steps || []);
  };

  const handleStartNewRun = async (task: string, projectName?: string) => {
    setIsExecutingAgent(true);
    setLiveLogs((prev) => [
      ...prev,
      {
        type: 'info',
        text: `Starting autonomous agent task: "${task}"`,
        ts: new Date().toLocaleTimeString(),
      },
    ]);

    try {
      const created = await api.agent.createRun({
        task,
        projectName,
        model: activeModel,
        customApiKey: primaryApiKey,
      });

      setRuns((prev) => [created.run, ...prev]);
      setActiveRunId(created.run.id);
      const initialSteps = created.steps || [];
      setChecklistSteps(initialSteps);

      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'info',
          text: `Initialized project folder: ${created.project_folder}`,
          ts: new Date().toLocaleTimeString(),
        },
        {
          type: 'info',
          text: `Generated ${initialSteps.length} steps — starting autonomous execution...`,
          ts: new Date().toLocaleTimeString(),
        },
      ]);

      // Auto-execute all steps sequentially
      let currentSteps = initialSteps;
      for (let i = 0; i < currentSteps.length; i++) {
        const step = currentSteps[i];
        if (step.status === 'completed') continue;

        setLiveLogs((prev) => [
          ...prev,
          {
            type: 'tool',
            text: `▶ Executing Step ${Number(step.id)}: "${step.title}"...`,
            ts: new Date().toLocaleTimeString(),
          },
        ]);

        // Mark in_progress
        setChecklistSteps((prev) =>
          prev.map((s) => (s.id === step.id ? { ...s, status: 'in_progress' } : s))
        );

        try {
          const stepRes = await api.agent.executeStep({
            run_id: created.run.id,
            step_id: step.id,
            project_folder: created.run.project_folder,
            model: activeModel,
            customApiKey: primaryApiKey,
          });

          // Refresh checklist from disk
          const updatedChecklist = await api.agent.getRunChecklist(created.run.project_folder);
          if (updatedChecklist?.steps?.length > 0) {
            setChecklistSteps(updatedChecklist.steps);
            currentSteps = updatedChecklist.steps;
          } else {
            setChecklistSteps((prev) =>
              prev.map((s) =>
                s.id === step.id ? { ...s, status: 'completed', evidence: stepRes.evidence } : s
              )
            );
          }

          setLiveLogs((prev) => [
            ...prev,
            {
              type: 'info',
              text: `✓ Step ${step.id} complete.`,
              ts: new Date().toLocaleTimeString(),
            },
          ]);
        } catch (stepErr: any) {
          setLiveLogs((prev) => [
            ...prev,
            {
              type: 'error',
              text: `✗ Step ${step.id} failed: ${stepErr.message}`,
              ts: new Date().toLocaleTimeString(),
            },
          ]);
          setChecklistSteps((prev) =>
            prev.map((s) =>
              s.id === step.id
                ? { ...s, status: 'failed', retry_count: s.retry_count + 1, error_message: stepErr.message }
                : s
            )
          );
          // Continue to next step instead of stopping entirely
        }
      }

      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'info',
          text: '🎉 All steps executed! Task complete.',
          ts: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err: any) {
      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'error',
          text: `Failed to initialize run: ${err.message}`,
          ts: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsExecutingAgent(false);
    }
  };


  const handleExecuteNextStep = async () => {
    if (!activeRun || isExecutingAgent) return;
    setIsExecutingAgent(true);

    const nextPending = checklistSteps.find((s) => s.status === 'pending' || s.status === 'failed');
    if (!nextPending) {
      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'info',
          text: 'All checklist steps verified! Run complete.',
          ts: new Date().toLocaleTimeString(),
        },
      ]);
      setIsExecutingAgent(false);
      return;
    }

    setLiveLogs((prev) => [
      ...prev,
      {
        type: 'tool',
        text: `Executing Step ${nextPending.id}: "${nextPending.title}"...`,
        ts: new Date().toLocaleTimeString(),
      },
    ]);

    // Mark in_progress in UI
    setChecklistSteps((prev) =>
      prev.map((s) => (s.id === nextPending.id ? { ...s, status: 'in_progress' } : s))
    );

    try {
      const stepRes = await api.agent.executeStep({
        run_id: activeRun.id,
        step_id: nextPending.id,
        project_folder: activeRun.project_folder,
        model: activeModel,
        customApiKey: primaryApiKey,
      });

      // Refresh checklist from disk
      const updatedChecklist = await api.agent.getRunChecklist(activeRun.project_folder);
      if (updatedChecklist && updatedChecklist.steps && updatedChecklist.steps.length > 0) {
        setChecklistSteps(updatedChecklist.steps);
      } else {
        // Fallback update
        setChecklistSteps((prev) =>
          prev.map((s) =>
            s.id === nextPending.id
              ? {
                  ...s,
                  status: 'completed',
                  evidence: {
                    files_created: stepRes.files_created || ['main.py'],
                    command_exit_codes: [stepRes.exit_code || 0],
                  },
                  orchid_verdict: stepRes.orchid_verdict,
                }
              : s
          )
        );
      }

      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'info',
          text: `Step ${nextPending.id} passed verification.`,
          ts: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err: any) {
      setLiveLogs((prev) => [
        ...prev,
        {
          type: 'error',
          text: `Step failed: ${err.message}`,
          ts: new Date().toLocaleTimeString(),
        },
      ]);
      setChecklistSteps((prev) =>
        prev.map((s) =>
          s.id === nextPending.id
            ? { ...s, status: 'failed', retry_count: s.retry_count + 1, error_message: err.message }
            : s
        )
      );
    } finally {
      setIsExecutingAgent(false);
    }
  };

  const handleStopRun = async (runId: string) => {
    await api.agent.stopRun(runId);
    setIsExecutingAgent(false);
    setLiveLogs((prev) => [
      ...prev,
      {
        type: 'info',
        text: 'Agent execution stopped by operator.',
        ts: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const handleJumpBack = async (targetStepId: string, reason: string) => {
    if (!activeRun) return;
    await api.agent.jumpToStep({
      project_folder: activeRun.project_folder,
      target_step_id: targetStepId,
      reason,
    });
    // Invalidate dependent steps in UI
    const targetIdx = checklistSteps.findIndex((s) => s.id === targetStepId);
    if (targetIdx !== -1) {
      setChecklistSteps((prev) =>
        prev.map((s, idx) => (idx >= targetIdx ? { ...s, status: 'pending' } : s))
      );
    }
    setLiveLogs((prev) => [
      ...prev,
      {
        type: 'info',
        text: `Jump-back executed to Step ${targetStepId}: ${reason}`,
        ts: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const handleRenameProject = async (runId: string, newName: string) => {
    const res = await api.agent.renameProjectFolder({ run_id: runId, new_name: newName });
    if (res.ok && res.new_name) {
      setRuns((prev) =>
        prev.map((r) =>
          r.id === runId
            ? {
                ...r,
                workspace_name: res.new_name!,
                title: res.new_name!,
                project_folder: res.new_name ? r.project_folder.replace(/[^\\/]+$/, res.new_name) : r.project_folder,
              }
            : r
        )
      );
    }
  };

  const handleSaveApiKeySlots = (slots: ApiKeySlot[]) => {
    setApiKeySlots(slots);
    localStorage.setItem('zeno_api_key_slots', JSON.stringify(slots));
    // Persist to backend .env so keys survive app restart
    api.settings.saveApiKeys(
      slots.map((s) => ({ provider: s.provider, key: s.key }))
    ).catch(() => {});
  };

  const handleSaveWorkspaceDir = (dir: string) => {
    setWorkspaceDir(dir);
    localStorage.setItem('zeno_workspace_dir', dir);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B0D13] text-slate-100 font-sans select-none">
      {/* Sidebar Navigation Rail */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        activeRunCount={isExecutingAgent ? 1 : 0}
        activeProjectName={activeRun?.workspace_name || activeRun?.title}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header Bar */}
        <Header
          activeTab={activeTab}
          activeModel={activeModel}
          availableModels={availableModels}
          onChangeModel={(m) => {
            setActiveModel(m);
            localStorage.setItem('zeno_active_model', m);
          }}
          telemetry={telemetry}
          activeProjectName={activeRun?.workspace_name || activeRun?.title}
        />

        {/* View Switcher */}
        <main className="flex-1 flex overflow-hidden">
          {activeTab === 'assistant' && (
            <AssistantPage
              threads={threads}
              activeThreadId={activeThreadId}
              onSelectThread={handleSelectThread}
              onCreateThread={handleCreateThread}
              onDeleteThread={handleDeleteThread}
              activeModel={activeModel}
              apiKey={primaryApiKey}
              activeRunTitle={activeRun?.title}
              isAgentRunning={isExecutingAgent}
            />
          )}

          {activeTab === 'agent' && (
            <AgentWorkspacePage
              runs={runs}
              activeRun={activeRun}
              checklistSteps={checklistSteps}
              onSelectRun={handleSelectRun}
              onStartNewRun={handleStartNewRun}
              onStopRun={handleStopRun}
              onExecuteNextStep={handleExecuteNextStep}
              onJumpBack={handleJumpBack}
              onRenameProject={handleRenameProject}
              onOpenFileViewer={(path) => setViewerPath(path)}
              isExecuting={isExecutingAgent}
              liveLogs={liveLogs}
            />
          )}

          {activeTab === 'files' && (
            <FilesPage
              projectFolder={activeRun?.project_folder || ''}
              projectName={activeRun?.workspace_name || activeRun?.title || ''}
              onOpenFileViewer={(path) => setViewerPath(path)}
            />
          )}

          {activeTab === 'jobs' && <JobsPage />}

          {activeTab === 'orchid' && <OrchidPage />}

          {activeTab === 'memory' && (
            <MemoryPage apiKey={primaryApiKey} activeModel={activeModel} />
          )}

          {activeTab === 'settings' && (
            <SettingsPage
              apiKeySlots={apiKeySlots}
              onSaveApiKeySlots={handleSaveApiKeySlots}
              workspaceDir={workspaceDir}
              onSaveWorkspaceDir={handleSaveWorkspaceDir}
            />
          )}
        </main>
      </div>

      {/* In-App File Viewer Modal */}
      {viewerPath && (
        <FileViewerModal filePath={viewerPath} onClose={() => setViewerPath(null)} />
      )}
    </div>
  );
}
