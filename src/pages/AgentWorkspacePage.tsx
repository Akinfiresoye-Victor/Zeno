import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Pause,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  ChevronRight,
  FileCode,
  ShieldCheck,
  ShieldAlert,
  Edit2,
  Folder,
  Terminal,
  Activity,
  Image as ImageIcon,
} from 'lucide-react';
import { AgentRunRecord, ChecklistStep, StepStatus } from '../types';
import { api } from '../services/api';

interface AgentWorkspacePageProps {
  runs: AgentRunRecord[];
  activeRun: AgentRunRecord | null;
  checklistSteps: ChecklistStep[];
  onSelectRun: (run: AgentRunRecord) => void;
  onStartNewRun: (task: string, projectName?: string) => Promise<void>;
  onStopRun: (runId: string) => Promise<void>;
  onExecuteNextStep: () => Promise<void>;
  onJumpBack: (targetStepId: string, reason: string) => Promise<void>;
  onRenameProject: (runId: string, newName: string) => Promise<void>;
  onOpenFileViewer: (path: string) => void;
  isExecuting: boolean;
  liveLogs: { type: string; text: string; ts: string }[];
}

export const AgentWorkspacePage: React.FC<AgentWorkspacePageProps> = ({
  runs,
  activeRun,
  checklistSteps,
  onSelectRun,
  onStartNewRun,
  onStopRun,
  onExecuteNextStep,
  onJumpBack,
  onRenameProject,
  onOpenFileViewer,
  isExecuting,
  liveLogs,
}) => {
  const [taskInput, setTaskInput] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [jumpStepId, setJumpStepId] = useState<string | null>(null);
  const [jumpReason, setJumpReason] = useState('');
  const [showLogs, setShowLogs] = useState(true);
  const logsBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (showLogs) {
      logsBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveLogs, showLogs]);

  const handleStart = async () => {
    const task = taskInput.trim();
    if (!task || isExecuting) return;
    setTaskInput('');
    await onStartNewRun(task);
  };

  const handleSaveRename = async () => {
    if (!activeRun || !renameValue.trim()) {
      setIsRenaming(false);
      return;
    }
    await onRenameProject(activeRun.id, renameValue.trim());
    setIsRenaming(false);
  };

  const handleConfirmJump = async () => {
    if (!jumpStepId) return;
    await onJumpBack(jumpStepId, jumpReason || 'Operator requested jump-back.');
    setJumpStepId(null);
    setJumpReason('');
  };

  const completedCount = checklistSteps.filter((s) => s.status === 'completed').length;
  const progressPercent =
    checklistSteps.length > 0 ? Math.round((completedCount / checklistSteps.length) * 100) : 0;

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0B0D13]">
      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Project Header Card */}
        <div className="p-4 border-b border-[#1F2637] bg-[#0E111A]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-mono">
                <Folder size={20} />
              </div>
              <div>
                {isRenaming ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      className="px-2 py-0.5 text-xs bg-[#151926] border border-indigo-500 rounded text-slate-100 font-mono outline-none"
                      autoFocus
                    />
                    <button
                      onClick={handleSaveRename}
                      className="px-2 py-0.5 text-xs bg-indigo-600 rounded text-white"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setIsRenaming(false)}
                      className="px-2 py-0.5 text-xs text-slate-400 hover:text-slate-200"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-semibold text-slate-100 font-mono">
                      {activeRun?.workspace_name || activeRun?.title || 'No Active Project'}
                    </h2>
                    {activeRun && (
                      <button
                        onClick={() => {
                          setRenameValue(activeRun.workspace_name || activeRun.title);
                          setIsRenaming(true);
                        }}
                        className="text-slate-500 hover:text-slate-300 transition"
                        title="Rename Project Folder"
                      >
                        <Edit2 size={12} />
                      </button>
                    )}
                  </div>
                )}
                <div className="text-[11px] text-slate-500 font-mono truncate max-w-lg mt-0.5">
                  {activeRun?.project_folder || 'Enter a task below to create a project workspace.'}
                </div>
              </div>
            </div>

            {/* Run Controls */}
            {activeRun && (
              <div className="flex items-center gap-2">
                {isExecuting ? (
                  <button
                    onClick={() => onStopRun(activeRun.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-medium transition"
                  >
                    <Square size={13} />
                    <span>Stop Agent</span>
                  </button>
                ) : (
                  <button
                    onClick={onExecuteNextStep}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
                  >
                    <Play size={13} />
                    <span>Run Next Step</span>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Progress Bar */}
          {activeRun && checklistSteps.length > 0 && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                <span>
                  Progress: {completedCount} of {checklistSteps.length} steps verified
                </span>
                <span className="font-mono">{progressPercent}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1A1F2C] overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-300 rounded-full"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Task Prompt Bar (when idle or adding new task) */}
        <div className="px-4 py-3 bg-[#0F121B] border-b border-[#1F2637]">
          <div className="flex items-center gap-2 bg-[#151926] border border-[#232B3E] rounded-xl px-3 py-2 focus-within:border-indigo-500 transition">
            <Terminal size={15} className="text-slate-400 shrink-0" />
            <input
              type="text"
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleStart()}
              placeholder="Give Zeno an autonomous engineering task (e.g. 'Build a 2D car racing game in Tkinter')..."
              className="flex-1 bg-transparent text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
            <button
              onClick={handleStart}
              disabled={isExecuting || !taskInput.trim()}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-medium transition shrink-0 flex items-center gap-1.5"
            >
              <Play size={12} />
              <span>Start Autonomous Agent</span>
            </button>
          </div>
        </div>

        {/* Checklist Steps Table */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {checklistSteps.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500">
              <Terminal size={32} className="text-slate-600 mb-2" />
              <p className="text-xs font-medium text-slate-400">No checklist initialized yet</p>
              <p className="text-[11px] max-w-sm mt-1">
                Start an agent run above. Zeno will plan a multi-step checklist, create an isolated
                project folder, initialize a Python virtual environment, and verify each step.
              </p>
            </div>
          ) : (
            checklistSteps.map((step, idx) => {
              const isCompleted = step.status === 'completed';
              const isInProgress = step.status === 'in_progress';
              const isFailed = step.status === 'failed';

              return (
                <div
                  key={step.id}
                  className={`p-3.5 rounded-xl border transition ${
                    isInProgress
                      ? 'bg-indigo-950/20 border-indigo-500/40 shadow-xs'
                      : isCompleted
                      ? 'bg-[#121622] border-[#222B3D]'
                      : isFailed
                      ? 'bg-red-950/20 border-red-500/30'
                      : 'bg-[#10131E] border-[#1C2333]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      {/* Status Icon */}
                      <div className="mt-0.5">
                        {isCompleted && <CheckCircle2 size={16} className="text-emerald-400" />}
                        {isInProgress && (
                          <div className="w-4 h-4 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                        )}
                        {isFailed && <AlertTriangle size={16} className="text-red-400" />}
                        {step.status === 'pending' && <Clock size={16} className="text-slate-500" />}
                        {step.status === 'skipped' && <span className="text-slate-600 text-xs">—</span>}
                      </div>

                      {/* Step Details */}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-100">
                            {idx + 1}. {step.title}
                          </span>
                          {step.retry_count > 0 && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono">
                              Retry {step.retry_count}/{step.max_retries}
                            </span>
                          )}
                        </div>

                        {/* Dependencies */}
                        {step.depends_on && step.depends_on.length > 0 && (
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            Depends on: {step.depends_on.join(', ')}
                          </div>
                        )}

                        {/* Evidence: Created files, test results, exit codes */}
                        {step.evidence && (
                          <div className="flex flex-wrap items-center gap-2 mt-2">
                            {step.evidence.files_created?.map((file: string) => (
                              <button
                                key={file}
                                onClick={() => onOpenFileViewer(file)}
                                className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#181E2E] hover:bg-[#222B40] border border-[#2B3650] text-[10px] font-mono text-slate-300 transition"
                              >
                                <FileCode size={11} className="text-indigo-400" />
                                <span>{file}</span>
                              </button>
                            ))}

                            {step.evidence.command_exit_codes?.map((code: number, cIdx: number) => (
                              <span
                                key={cIdx}
                                className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                                  code === 0
                                    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                    : 'bg-red-500/10 text-red-300 border-red-500/20'
                                }`}
                              >
                                Exit: {code}
                              </span>
                            ))}

                            {step.evidence.screenshot_path && (
                              <button
                                onClick={() => onOpenFileViewer(step.evidence.screenshot_path!)}
                                className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-[10px] text-indigo-300"
                              >
                                <ImageIcon size={11} />
                                <span>Screenshot</span>
                              </button>
                            )}
                          </div>
                        )}

                        {/* Orchid Verdict Record */}
                        {step.orchid_verdict && (
                          <div className="flex items-center gap-1.5 mt-2 text-[10px]">
                            <ShieldCheck size={12} className="text-emerald-400" />
                            <span className="text-slate-400">Orchid:</span>
                            <span className="font-mono text-emerald-300">{step.orchid_verdict.rule}</span>
                            <span className="text-slate-500">— {step.orchid_verdict.reason}</span>
                          </div>
                        )}

                        {/* Error Message if any */}
                        {step.error_message && (
                          <div className="mt-2 text-[11px] text-red-400 bg-red-950/30 border border-red-500/20 p-2 rounded">
                            {step.error_message}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Step Action: Jump-Back (Rule C) */}
                    {isCompleted && (
                      <button
                        onClick={() => {
                          setJumpStepId(step.id);
                          setJumpReason(`Re-verifying from step: ${step.title}`);
                        }}
                        className="text-[11px] px-2.5 py-1 rounded bg-[#181E2E] hover:bg-indigo-600/20 text-slate-400 hover:text-indigo-300 border border-[#2B3650] flex items-center gap-1 transition shrink-0"
                        title="Re-verify step and invalidate dependent steps"
                      >
                        <RotateCcw size={11} />
                        <span>Re-verify from here</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Live Execution Logs Drawer (Rule D & G) */}
        <div className="border-t border-[#1F2637] bg-[#0A0C12]">
          <div className="px-4 py-2 flex items-center justify-between border-b border-[#181D2B]">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Terminal size={13} className="text-indigo-400" />
              <span className="font-semibold text-slate-300">Live Agent Logs</span>
              <span className="text-[10px] font-mono text-slate-500">({liveLogs.length} entries)</span>
            </div>
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="text-[11px] text-slate-500 hover:text-slate-300 transition"
            >
              {showLogs ? 'Collapse' : 'Expand'}
            </button>
          </div>

          {showLogs && (
            <div className="h-40 overflow-y-auto p-3 font-mono text-[11px] space-y-1 bg-[#07090E]">
              {liveLogs.length === 0 ? (
                <div className="text-slate-600 italic">No execution logs yet.</div>
              ) : (
                liveLogs.map((log, lIdx) => (
                  <div key={lIdx} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-slate-600 shrink-0">[{log.ts}]</span>
                    <span
                      className={
                        log.type === 'tool'
                          ? 'text-indigo-300'
                          : log.type === 'retry'
                          ? 'text-amber-300'
                          : log.type === 'error'
                          ? 'text-red-400'
                          : 'text-slate-300'
                      }
                    >
                      {log.text}
                    </span>
                  </div>
                ))
              )}
              <div ref={logsBottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Past Runs Queue Sidebar */}
      <div className="w-64 border-l border-[#1F2637] bg-[#0E111A] flex flex-col shrink-0">
        <div className="p-3 border-b border-[#1F2637] text-xs font-semibold text-slate-300">
          Agent Run History
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {runs.map((r) => {
            const isSelected = r.id === activeRun?.id;
            return (
              <div
                key={r.id}
                onClick={() => onSelectRun(r)}
                className={`p-2.5 rounded-lg border cursor-pointer transition ${
                  isSelected
                    ? 'bg-[#181D2B] border-indigo-500/40'
                    : 'bg-[#121520] border-[#22293B] hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between text-xs font-medium text-slate-200">
                  <span className="truncate">{r.title}</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded font-mono uppercase ${
                      r.status === 'completed'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : r.status === 'active'
                        ? 'bg-indigo-500/20 text-indigo-300 animate-pulse'
                        : 'bg-slate-700 text-slate-300'
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 truncate mt-1">{r.task_prompt}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Jump-Back Confirmation Modal (Rule C) */}
      {jumpStepId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-[#121520] border border-[#2B354C] rounded-2xl p-5 shadow-2xl">
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <RotateCcw size={16} className="text-indigo-400" />
              <span>Step Jump-Back & Invalidation</span>
            </h3>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Jumping back will mark this step and any dependent steps as <strong>pending</strong>.
              Completed steps that do not depend on this step will be preserved.
            </p>
            <div className="mt-4">
              <label className="text-[11px] text-slate-400 block mb-1">Reason for Jump-Back:</label>
              <input
                type="text"
                value={jumpReason}
                onChange={(e) => setJumpReason(e.target.value)}
                placeholder="e.g. Bug found in core module requirements"
                className="w-full px-3 py-2 text-xs bg-[#1A1F2E] border border-[#2B354C] rounded-lg text-slate-200 outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setJumpStepId(null)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmJump}
                className="px-4 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white font-medium"
              >
                Confirm Jump-Back
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
