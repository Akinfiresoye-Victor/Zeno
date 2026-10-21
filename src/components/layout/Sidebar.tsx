import React from 'react';
import {
  MessageSquare,
  Bot,
  FolderOpen,
  Activity,
  ShieldCheck,
  BrainCircuit,
  Settings,
  Terminal,
} from 'lucide-react';
import { NavigationTab } from '../../types';

interface SidebarProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  activeRunCount?: number;
  activeJobCount?: number;
  pendingApprovalCount?: number;
  activeProjectName?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  activeRunCount = 0,
  activeJobCount = 0,
  pendingApprovalCount = 0,
  activeProjectName = '',
}) => {
  const navItems = [
    {
      id: 'assistant' as NavigationTab,
      label: 'Assistant',
      icon: MessageSquare,
      badge: null,
    },
    {
      id: 'agent' as NavigationTab,
      label: 'Agent Workspace',
      icon: Bot,
      badge: activeRunCount > 0 ? `${activeRunCount} Active` : null,
      badgeColor: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    },
    {
      id: 'files' as NavigationTab,
      label: 'Files',
      icon: FolderOpen,
      badge: null,
    },
    {
      id: 'jobs' as NavigationTab,
      label: 'Jobs & Processes',
      icon: Activity,
      badge: activeJobCount > 0 ? `${activeJobCount}` : null,
      badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    },
    {
      id: 'orchid' as NavigationTab,
      label: 'Orchid Security',
      icon: ShieldCheck,
      badge: pendingApprovalCount > 0 ? `${pendingApprovalCount} Review` : null,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    },
    {
      id: 'memory' as NavigationTab,
      label: 'Memory',
      icon: BrainCircuit,
      badge: null,
    },
    {
      id: 'settings' as NavigationTab,
      label: 'Settings',
      icon: Settings,
      badge: null,
    },
  ];

  return (
    <aside className="w-64 bg-[#0F121B] border-r border-[#1F2637] flex flex-col select-none shrink-0">
      {/* Brand Header */}
      <div className="h-14 px-4 flex items-center gap-3 border-b border-[#1F2637]">
        <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold font-mono text-base">
          Z
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-slate-100 tracking-tight">Zeno Desktop</span>
          <span className="text-[10px] text-slate-500 font-medium">Autonomous AI Assistant</span>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-2.5 py-4 space-y-1 overflow-y-auto">
        <div className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-xs'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#181D2B] border border-transparent'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon size={16} className={isActive ? 'text-indigo-400' : 'text-slate-400'} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full border font-mono ${item.badgeColor}`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Active Project Footer Widget */}
      {activeProjectName && (
        <div className="p-3 mx-2.5 mb-3 rounded-lg bg-[#151926] border border-[#232B3E]">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-medium uppercase tracking-wider mb-1">
            <Terminal size={11} className="text-indigo-400" />
            <span>Active Project</span>
          </div>
          <div className="text-xs font-mono text-slate-200 truncate font-medium">
            {activeProjectName}
          </div>
        </div>
      )}

      {/* Version and System State */}
      <div className="px-4 py-3 border-t border-[#1F2637] flex items-center justify-between text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>Local Engine Ready</span>
        </div>
        <span className="font-mono text-[10px] text-slate-600">v2.4.0</span>
      </div>
    </aside>
  );
};
