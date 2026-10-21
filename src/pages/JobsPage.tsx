import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Square,
  Terminal,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Trash2,
} from 'lucide-react';
import { JobRecord } from '../types';
import { api } from '../services/api';

export const JobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [checkedJobIds, setCheckedJobIds] = useState<Set<string>>(new Set());
  const [jobLogs, setJobLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logsBottomRef = useRef<HTMLDivElement>(null);

  const fetchJobs = async () => {
    try {
      const list = await api.jobs.listJobs();
      setJobs(list || []);
      if (!selectedJobId && list && list.length > 0) {
        setSelectedJobId(list[0].job_id);
      }
    } catch (err) {
      console.error('Failed to list background jobs:', err);
    }
  };

  const fetchLogs = async (jobId: string) => {
    try {
      const res = await api.jobs.getJobLogs(jobId, 300);
      setJobLogs(res.logs || []);
    } catch (err) {
      console.error('Failed to get job logs:', err);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchJobs();
        if (selectedJobId) {
          fetchLogs(selectedJobId);
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [selectedJobId, autoRefresh]);

  useEffect(() => {
    if (selectedJobId) {
      fetchLogs(selectedJobId);
    }
  }, [selectedJobId]);

  useEffect(() => {
    logsBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [jobLogs]);

  const handleStopJob = async (jobId: string) => {
    await api.jobs.stopJob(jobId);
    await fetchJobs();
    if (selectedJobId === jobId) {
      await fetchLogs(jobId);
    }
  };

  const toggleCheck = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = new Set(checkedJobIds);
    if (updated.has(id)) {
      updated.delete(id);
    } else {
      updated.add(id);
    }
    setCheckedJobIds(updated);
  };

  const toggleCheckAll = () => {
    if (checkedJobIds.size === jobs.length && jobs.length > 0) {
      setCheckedJobIds(new Set());
    } else {
      setCheckedJobIds(new Set(jobs.map((j) => j.job_id)));
    }
  };

  const handleDeleteSelected = async () => {
    if (checkedJobIds.size === 0) return;
    await api.delete.jobs(Array.from(checkedJobIds));
    setCheckedJobIds(new Set());
    await fetchJobs();
    setJobLogs([]);
  };

  const handleClearAll = async () => {
    await api.delete.jobs();
    setCheckedJobIds(new Set());
    await fetchJobs();
    setJobLogs([]);
  };

  const selectedJob = jobs.find((j) => j.job_id === selectedJobId) || jobs[0];

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0B0D13]">
      {/* Jobs List Area */}
      <div className="w-1/2 border-r border-[#1F2637] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-[#1F2637] bg-[#0E111A] flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <Activity size={16} className="text-emerald-400" />
              <span>Process Supervisor</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                {jobs.filter((j) => j.status === 'running').length} Running
              </span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Tracks server daemons, GUI runners, and executes process-tree kills.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {checkedJobIds.size > 0 && (
              <button
                onClick={handleDeleteSelected}
                className="px-2.5 py-1 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-[11px] font-medium flex items-center gap-1 transition"
              >
                <Trash2 size={12} />
                <span>Delete ({checkedJobIds.size})</span>
              </button>
            )}

            {jobs.length > 0 && (
              <button
                onClick={handleClearAll}
                className="px-2.5 py-1 rounded-lg bg-[#181D2B] hover:bg-red-950/30 text-slate-400 hover:text-red-300 border border-[#2B354C] text-[11px] font-medium flex items-center gap-1 transition"
                title="Stop and clear all jobs"
              >
                <Trash2 size={12} />
                <span>Clear All</span>
              </button>
            )}

            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-[11px] px-2.5 py-1 rounded-lg border font-mono transition ${
                autoRefresh
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-[#151926] text-slate-500 border-[#232B3E]'
              }`}
            >
              {autoRefresh ? 'Live' : 'Paused'}
            </button>
            <button
              onClick={fetchJobs}
              className="p-1.5 rounded-lg bg-[#151926] hover:bg-[#1C2233] border border-[#232B3E] text-slate-400 hover:text-slate-200 transition"
              title="Refresh Jobs"
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Master Select All Bar */}
        {jobs.length > 0 && (
          <div className="px-4 py-2 bg-[#0E111A] border-b border-[#181D2B] flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={checkedJobIds.size === jobs.length && jobs.length > 0}
              onChange={toggleCheckAll}
              className="rounded cursor-pointer accent-indigo-600"
            />
            <span className="text-[11px]">Select All Jobs</span>
          </div>
        )}

        {/* Jobs Table */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center text-slate-500">
              <Activity size={36} className="text-slate-600 mb-2" />
              <p className="text-xs font-medium text-slate-400">No active background jobs</p>
              <p className="text-[11px] max-w-xs text-slate-500 mt-1">
                When the agent starts a web server, GUI window, or background worker, it will appear here with its real OS process tree.
              </p>
            </div>
          ) : (
            jobs.map((job) => {
              const isSelected = job.job_id === selectedJobId;
              const isChecked = checkedJobIds.has(job.job_id);
              const isRunning = job.status === 'running';

              return (
                <div
                  key={job.job_id}
                  onClick={() => setSelectedJobId(job.job_id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition ${
                    isSelected
                      ? 'bg-[#151926] border-indigo-500/50 shadow-xs'
                      : 'bg-[#10131E] border-[#1F2637] hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onClick={(e) => toggleCheck(job.job_id, e)}
                        onChange={() => {}}
                        className="mt-1 rounded cursor-pointer accent-indigo-600"
                      />

                      <div className="mt-0.5">
                        {isRunning ? (
                          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                        ) : job.status === 'completed' || job.status === 'finished' ? (
                          <CheckCircle2 size={14} className="text-emerald-400" />
                        ) : (
                          <AlertTriangle size={14} className="text-slate-500" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-slate-200 font-medium">
                            PID {job.pid || '—'}
                          </span>
                          <span
                            className={`text-[9px] font-mono px-1.5 py-0.2 rounded uppercase ${
                              isRunning
                                ? 'bg-emerald-500/15 text-emerald-300'
                                : 'bg-slate-700 text-slate-300'
                            }`}
                          >
                            {job.status}
                          </span>
                        </div>
                        <div className="font-mono text-xs text-slate-300 mt-1 truncate max-w-sm">
                          {job.command}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5 truncate max-w-sm">
                          cwd: {job.cwd}
                        </div>
                      </div>
                    </div>

                    {isRunning && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStopJob(job.job_id);
                        }}
                        className="px-2.5 py-1 rounded bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-[11px] font-medium flex items-center gap-1 transition"
                        title="Kill entire process tree"
                      >
                        <Square size={11} />
                        <span>Stop</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Process Terminal Output Column */}
      <div className="w-1/2 flex flex-col overflow-hidden bg-[#07090E]">
        <div className="p-3 border-b border-[#1F2637] bg-[#0E111A] flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
            <Terminal size={14} className="text-indigo-400" />
            <span>
              {selectedJob ? `Process Terminal [PID ${selectedJob.pid || '—'}]` : 'Process Output'}
            </span>
          </div>
          {selectedJob && (
            <span className="text-[10px] font-mono text-slate-500 truncate max-w-xs">
              {selectedJob.started_at}
            </span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1">
          {jobLogs.length === 0 ? (
            <div className="text-slate-600 italic">No console output recorded for this job.</div>
          ) : (
            jobLogs.map((line, idx) => (
              <div key={idx} className="text-slate-300 leading-relaxed whitespace-pre-wrap">
                {line}
              </div>
            ))
          )}
          <div ref={logsBottomRef} />
        </div>
      </div>
    </div>
  );
};
