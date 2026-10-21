import React from 'react';
import { Cpu, Battery, Sparkles, Minus, Square, X } from 'lucide-react';
import { NavigationTab, SystemTelemetry } from '../../types';

interface HeaderProps {
  activeTab: NavigationTab;
  activeModel: string;
  availableModels: string[];
  onChangeModel: (model: string) => void;
  telemetry: SystemTelemetry | null;
  activeProjectName?: string;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  activeModel,
  availableModels,
  onChangeModel,
  telemetry,
  activeProjectName,
}) => {
  const titles: Record<NavigationTab, { title: string; subtitle: string }> = {
    assistant: {
      title: 'Chat Assistant',
      subtitle: 'Conversational partner & agent run inspector',
    },
    agent: {
      title: 'Agent Workspace',
      subtitle: 'Autonomous checklist engine, verification & jump-back',
    },
    files: {
      title: 'Workspace Files',
      subtitle: 'Contained project files, previews & reveal',
    },
    jobs: {
      title: 'Job Supervisor',
      subtitle: 'Live process manager & full process-tree termination',
    },
    orchid: {
      title: 'Orchid Security Kernel',
      subtitle: 'Layered security rules, audit log & human approvals',
    },
    memory: {
      title: 'Persistent Memory',
      subtitle: 'Workspace profile, preferences & AI context synthesis',
    },
    settings: {
      title: 'Settings & Keys',
      subtitle: 'Multi-provider key slots & workspace folder configuration',
    },
  };

  const current = titles[activeTab];

  return (
    <header className="h-14 bg-[#0F121B] border-b border-[#1F2637] px-6 flex items-center justify-between select-none shrink-0">
      {/* Title & View Context */}
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <span>{current.title}</span>
            {activeProjectName && activeTab === 'agent' && (
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                {activeProjectName}
              </span>
            )}
          </h1>
          <p className="text-[11px] text-slate-500 font-normal leading-tight">
            {current.subtitle}
          </p>
        </div>
      </div>

      {/* Center/Right Controls: Model Selector & Telemetry */}
      <div className="flex items-center gap-3">
        {/* Model Selector */}
        <div className="flex items-center gap-2 bg-[#151926] border border-[#232B3E] px-2.5 py-1.5 rounded-lg">
          <Sparkles size={13} className="text-indigo-400" />
          <select
            value={activeModel}
            onChange={(e) => onChangeModel(e.target.value)}
            className="bg-transparent text-xs text-slate-200 outline-none cursor-pointer pr-1"
          >
            {availableModels.length > 0 ? (
              availableModels.map((m) => (
                <option key={m} value={m} className="bg-[#151926] text-slate-200">
                  {m}
                </option>
              ))
            ) : (
              <option value="gemini-3.5-flash-lite" className="bg-[#151926] text-slate-200">
                gemini-3.5-flash-lite
              </option>
            )}
          </select>
        </div>

        {/* Telemetry Indicator */}
        {telemetry && (
          <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-[#151926] border border-[#232B3E] text-xs text-slate-400">
            <div className="flex items-center gap-1">
              <Cpu size={12} className="text-slate-400" />
              <span>{telemetry.cpu_percent}% CPU</span>
            </div>
            <span className="text-slate-700">|</span>
            <div className="flex items-center gap-1">
              <Battery size={12} className="text-slate-400" />
              <span>{telemetry.battery.split(' ')[0]}</span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
