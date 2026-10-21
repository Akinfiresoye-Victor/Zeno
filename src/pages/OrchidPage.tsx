import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  Clock,
  Terminal,
  FileCode,
  Trash2,
} from 'lucide-react';
import { OrchidEvaluation, PendingApproval } from '../types';
import { api } from '../services/api';

export const OrchidPage: React.FC = () => {
  const [evaluations, setEvaluations] = useState<OrchidEvaluation[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [evals, approvals] = await Promise.all([
        api.orchid.listEvaluations(100),
        api.orchid.listPendingApprovals(),
      ]);
      setEvaluations(evals || []);
      setPendingApprovals(approvals || []);
      setSelectedIndices(new Set());
    } catch (err) {
      console.error('Failed to load Orchid safety data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleDecision = async (approvalId: string, decision: 'APPROVE' | 'DENY') => {
    await api.orchid.decideApproval(approvalId, decision);
    await fetchData();
  };

  const toggleSelect = (index: number) => {
    const updated = new Set(selectedIndices);
    if (updated.has(index)) {
      updated.delete(index);
    } else {
      updated.add(index);
    }
    setSelectedIndices(updated);
  };

  const toggleSelectAll = () => {
    if (selectedIndices.size === evaluations.length && evaluations.length > 0) {
      setSelectedIndices(new Set());
    } else {
      setSelectedIndices(new Set(evaluations.map((_, i) => i)));
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedIndices.size === 0) return;
    // Remove selected from state and clear on backend
    const remaining = evaluations.filter((_, idx) => !selectedIndices.has(idx));
    setEvaluations(remaining);
    setSelectedIndices(new Set());
    await api.delete.orchidLogs();
  };

  const handleClearAll = async () => {
    setEvaluations([]);
    setSelectedIndices(new Set());
    await api.delete.orchidLogs();
  };

  const allowedCount = evaluations.filter((e) => e.verdict === 'ALLOW').length;
  const deniedCount = evaluations.filter((e) => e.verdict === 'DENY').length;
  const askCount = evaluations.filter((e) => e.verdict === 'ASK_USER').length;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#0B0D13]">
      {/* Header & Stats Cards */}
      <div className="p-4 border-b border-[#1F2637] bg-[#0E111A]">
        <div className="flex flex-wrap items-center justify-between mb-4 gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-400" />
              <span>Orchid Security Kernel</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Zero-bypass security policy kernel. Pre-approves safe commands, enforces project containment, and halts destructive behavior.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {selectedIndices.size > 0 && (
              <button
                onClick={handleDeleteSelected}
                className="px-2.5 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-medium flex items-center gap-1.5 transition"
              >
                <Trash2 size={13} />
                <span>Delete Selected ({selectedIndices.size})</span>
              </button>
            )}

            {evaluations.length > 0 && (
              <button
                onClick={handleClearAll}
                className="px-2.5 py-1.5 rounded-lg bg-[#181D2B] hover:bg-red-950/30 text-slate-400 hover:text-red-300 border border-[#2B354C] text-xs font-medium flex items-center gap-1.5 transition"
                title="Clear all evaluation logs"
              >
                <Trash2 size={13} />
                <span>Clear All Logs</span>
              </button>
            )}

            <button
              onClick={fetchData}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-[#151926] hover:bg-[#1C2233] border border-[#232B3E] text-slate-400 hover:text-slate-200 transition"
              title="Refresh Logs"
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#121520] border border-[#1F2637]">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
              Total Evaluated
            </div>
            <div className="text-lg font-bold font-mono text-slate-100 mt-1">
              {evaluations.length}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-[#121520] border border-[#1F2637]">
            <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-semibold flex items-center gap-1">
              <CheckCircle2 size={12} />
              <span>Allowed Safe</span>
            </div>
            <div className="text-lg font-bold font-mono text-emerald-300 mt-1">{allowedCount}</div>
          </div>

          <div className="p-3 rounded-xl bg-[#121520] border border-[#1F2637]">
            <div className="text-[10px] text-red-400 uppercase tracking-wider font-semibold flex items-center gap-1">
              <XCircle size={12} />
              <span>Blocked Destructive</span>
            </div>
            <div className="text-lg font-bold font-mono text-red-300 mt-1">{deniedCount}</div>
          </div>

          <div className="p-3 rounded-xl bg-[#121520] border border-[#1F2637]">
            <div className="text-[10px] text-amber-400 uppercase tracking-wider font-semibold flex items-center gap-1">
              <HelpCircle size={12} />
              <span>Operator Escalated</span>
            </div>
            <div className="text-lg font-bold font-mono text-amber-300 mt-1">{askCount}</div>
          </div>
        </div>
      </div>

      {/* Pending Human Approval Banner */}
      {pendingApprovals.length > 0 && (
        <div className="p-4 bg-amber-950/20 border-b border-amber-500/30">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-300 mb-2">
            <AlertTriangle size={15} />
            <span>Human Review Required ({pendingApprovals.length} pending actions)</span>
          </div>
          <div className="space-y-2">
            {pendingApprovals.map((appr) => (
              <div
                key={appr.id}
                className="p-3 rounded-lg bg-[#141824] border border-amber-500/30 flex items-center justify-between"
              >
                <div>
                  <div className="text-xs font-mono text-slate-200">
                    Rule: <strong className="text-amber-300">{appr.rule_name}</strong>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{appr.reason}</div>
                  <div className="text-[10px] font-mono text-slate-500 mt-1">
                    Target: {JSON.stringify(appr.payload)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDecision(appr.id, 'DENY')}
                    className="px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-medium"
                  >
                    Deny
                  </button>
                  <button
                    onClick={() => handleDecision(appr.id, 'APPROVE')}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
                  >
                    Approve
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evaluations Table */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="bg-[#121520] border border-[#1F2637] rounded-xl overflow-hidden shadow-xs">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#1F2637] bg-[#0F121B] text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
                <th className="py-2.5 px-3 w-8">
                  <input
                    type="checkbox"
                    checked={selectedIndices.size === evaluations.length && evaluations.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer accent-indigo-600"
                  />
                </th>
                <th className="py-2.5 px-4">Verdict</th>
                <th className="py-2.5 px-4">Rule Name</th>
                <th className="py-2.5 px-4">Action / Target</th>
                <th className="py-2.5 px-4">Reason</th>
                <th className="py-2.5 px-4 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#181D2B]">
              {evaluations.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 italic">
                    No safety evaluations recorded yet.
                  </td>
                </tr>
              ) : (
                evaluations.map((ev, idx) => {
                  const isChecked = selectedIndices.has(idx);
                  return (
                    <tr
                      key={idx}
                      className={`hover:bg-[#161B29] transition ${isChecked ? 'bg-indigo-950/20' : ''}`}
                    >
                      <td className="py-2.5 px-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelect(idx)}
                          className="rounded cursor-pointer accent-indigo-600"
                        />
                      </td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                            ev.verdict === 'ALLOW'
                              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                              : ev.verdict === 'DENY'
                              ? 'bg-red-500/15 text-red-300 border-red-500/30'
                              : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                          }`}
                        >
                          {ev.verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-slate-300 font-medium">
                        {ev.rule_name}
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="font-mono text-slate-200 truncate max-w-xs">
                          {ev.action_target}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">{ev.action_type}</div>
                      </td>
                      <td className="py-2.5 px-4 text-slate-400 max-w-sm truncate">{ev.reason}</td>
                      <td className="py-2.5 px-4 text-right font-mono text-[10px] text-slate-500">
                        {ev.timestamp.split('T')[1]?.slice(0, 8) || ev.timestamp}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
