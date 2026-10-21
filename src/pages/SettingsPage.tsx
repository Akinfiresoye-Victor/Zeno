import React, { useState, useEffect } from 'react';
import {
  Settings,
  Key,
  Folder,
  Eye,
  EyeOff,
  Save,
  Check,
  Shield,
  FileCode,
  Terminal,
  Globe,
  Camera,
  Clipboard,
  ExternalLink,
  Cpu,
  Lock,
} from 'lucide-react';
import { ApiKeySlot } from '../types';
import { api } from '../services/api';

interface SettingsPageProps {
  apiKeySlots: ApiKeySlot[];
  onSaveApiKeySlots: (slots: ApiKeySlot[]) => void;
  workspaceDir: string;
  onSaveWorkspaceDir: (dir: string) => void;
}

interface PermissionItem {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  defaultAllowed: boolean;
  category: 'core' | 'system' | 'network';
}

const PERMISSION_DEFINITIONS: PermissionItem[] = [
  {
    id: 'file_read',
    title: 'Read Project Files',
    description: 'Inspect source code, configs, and assets strictly within project directories.',
    icon: <FileCode size={15} className="text-blue-400" />,
    defaultAllowed: true,
    category: 'core',
  },
  {
    id: 'file_write',
    title: 'Write & Edit Project Files',
    description: 'Create, edit, and delete files inside active project folders. Sandbox prevents writing to OS root.',
    icon: <Folder size={15} className="text-emerald-400" />,
    defaultAllowed: true,
    category: 'core',
  },
  {
    id: 'python_exec',
    title: 'Isolated Python Execution',
    description: 'Run scripts and pytest suites inside isolated project .venv environments.',
    icon: <Terminal size={15} className="text-amber-400" />,
    defaultAllowed: true,
    category: 'core',
  },
  {
    id: 'web_search',
    title: 'Web & API Search',
    description: 'Fetch package documentation, API references, and stack traces via DuckDuckGo.',
    icon: <Globe size={15} className="text-indigo-400" />,
    defaultAllowed: true,
    category: 'network',
  },
  {
    id: 'dev_tools',
    title: 'Process & Diagnostic Telemetry',
    description: 'Inspect terminal exit codes, process statuses, and system load for debugging.',
    icon: <Cpu size={15} className="text-purple-400" />,
    defaultAllowed: true,
    category: 'system',
  },
  {
    id: 'screen_capture',
    title: 'Screen & Window Diagnostics',
    description: 'Take screenshots of running web apps or desktop windows for visual QA inspection.',
    icon: <Camera size={15} className="text-pink-400" />,
    defaultAllowed: false,
    category: 'system',
  },
  {
    id: 'clipboard',
    title: 'Clipboard Access',
    description: 'Read copied snippets or write generated code directly to system clipboard.',
    icon: <Clipboard size={15} className="text-cyan-400" />,
    defaultAllowed: false,
    category: 'system',
  },
  {
    id: 'app_launch',
    title: 'Launch External Applications',
    description: 'Trigger external tools such as VS Code, browser previews, or Windows File Explorer.',
    icon: <ExternalLink size={15} className="text-orange-400" />,
    defaultAllowed: false,
    category: 'system',
  },
];

export const SettingsPage: React.FC<SettingsPageProps> = ({
  apiKeySlots,
  onSaveApiKeySlots,
  workspaceDir,
  onSaveWorkspaceDir,
}) => {
  const [slots, setSlots] = useState<ApiKeySlot[]>(apiKeySlots);
  const [workspace, setWorkspace] = useState(workspaceDir);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState('');
  const [permissions, setPermissions] = useState<Record<string, boolean>>({
    file_read: true,
    file_write: true,
    python_exec: true,
    web_search: true,
    screen_capture: false,
    clipboard: false,
    app_launch: false,
    dev_tools: true,
  });

  useEffect(() => {
    let mounted = true;
    api.settings.getPermissions().then((perms) => {
      if (mounted && perms) {
        setPermissions((prev) => ({ ...prev, ...perms }));
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleKeyChange = (id: string, newKey: string) => {
    setSlots((prev) => prev.map((s) => (s.id === id ? { ...s, key: newKey } : s)));
  };

  const handleProviderChange = (id: string, newProvider: any) => {
    setSlots((prev) => prev.map((s) => (s.id === id ? { ...s, provider: newProvider } : s)));
  };

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleTogglePermission = async (id: string) => {
    const nextVal = !permissions[id];
    const updated = { ...permissions, [id]: nextVal };
    setPermissions(updated);
    await api.settings.savePermissions(updated);
  };

  const handleSave = async () => {
    onSaveApiKeySlots(slots);
    onSaveWorkspaceDir(workspace);
    await api.settings.savePermissions(permissions);
    setToast('Settings and permissions saved successfully!');
    setTimeout(() => setToast(''), 3000);
  };

  const providers = ['Gemini', 'Anthropic Claude', 'OpenRouter', 'OpenAI', 'Groq'] as const;

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0B0D13]">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1F2637]">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <Settings size={16} className="text-indigo-400" />
              <span>Settings & Configuration</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Manage multi-provider API keys, workspace directories, and agent system permissions.
            </p>
          </div>
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1.5 transition shadow-xs"
          >
            <Save size={13} />
            <span>Save All</span>
          </button>
        </div>

        {toast && (
          <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center gap-2 animate-in fade-in duration-200">
            <Check size={14} className="text-emerald-400" />
            <span>{toast}</span>
          </div>
        )}

        {/* System & Agent Permissions */}
        <div className="p-5 rounded-2xl bg-[#121520] border border-[#1F2637] space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
              <Lock size={14} className="text-indigo-400" />
              <span>Agent System Permissions</span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              Orchid Kernel Enforced
            </span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Select the exact capabilities and system permissions granted to Zeno agent runs. Changes take effect immediately.
          </p>

          <div className="grid grid-cols-1 gap-2.5 mt-3">
            {PERMISSION_DEFINITIONS.map((perm) => {
              const isEnabled = permissions[perm.id] ?? perm.defaultAllowed;
              return (
                <div
                  key={perm.id}
                  onClick={() => handleTogglePermission(perm.id)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                    isEnabled
                      ? 'bg-[#151a28] border-indigo-500/40 hover:border-indigo-500/60'
                      : 'bg-[#0F121B] border-[#1F2637] hover:border-[#2B354C] opacity-75'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-[#181D2B] border border-[#232B3E] shrink-0 mt-0.5">
                      {perm.icon}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-200">{perm.title}</span>
                        <span
                          className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                            isEnabled
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}
                        >
                          {isEnabled ? 'GRANTED' : 'REVOKED'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
                        {perm.description}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0">
                    <div
                      className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 ease-in-out ${
                        isEnabled ? 'bg-indigo-600' : 'bg-slate-700'
                      }`}
                    >
                      <div
                        className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 ease-in-out ${
                          isEnabled ? 'translate-x-4' : 'translate-x-0'
                        }`}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* API Key Slots */}
        <div className="p-5 rounded-2xl bg-[#121520] border border-[#1F2637] space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <Key size={14} className="text-indigo-400" />
            <span>API Key Slots (Flexible Multi-Provider)</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Configure up to 3 API keys. Models will be dynamically enabled based on valid keys.
          </p>

          <div className="space-y-3 mt-3">
            {slots.map((slot, idx) => (
              <div
                key={slot.id}
                className="p-3.5 rounded-xl bg-[#0F121B] border border-[#1F2637] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-300">Key Slot {idx + 1}</span>
                  <select
                    value={slot.provider}
                    onChange={(e) => handleProviderChange(slot.id, e.target.value)}
                    className="bg-[#181D2B] border border-[#2B354C] rounded px-2 py-1 text-xs text-slate-200 outline-none cursor-pointer"
                  >
                    {providers.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2 bg-[#151926] border border-[#232B3E] rounded-lg px-2.5 py-1.5 focus-within:border-indigo-500">
                  <input
                    type={showKeys[slot.id] ? 'text' : 'password'}
                    value={slot.key}
                    onChange={(e) => handleKeyChange(slot.id, e.target.value)}
                    placeholder={`Enter ${slot.provider} API key...`}
                    className="flex-1 bg-transparent text-xs text-slate-200 outline-none font-mono placeholder-slate-600"
                  />
                  <button
                    onClick={() => toggleShowKey(slot.id)}
                    className="text-slate-500 hover:text-slate-300"
                    title={showKeys[slot.id] ? 'Hide Key' : 'Show Key'}
                  >
                    {showKeys[slot.id] ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Workspace Directory */}
        <div className="p-5 rounded-2xl bg-[#121520] border border-[#1F2637] space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <Folder size={14} className="text-indigo-400" />
            <span>Workspace Root Directory (Rule B)</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            All agent project folders will be created inside this workspace directory. Zero files are written outside.
          </p>
          <div className="flex items-center gap-2 bg-[#0F121B] border border-[#1F2637] rounded-lg px-3 py-2">
            <input
              type="text"
              value={workspace}
              onChange={(e) => setWorkspace(e.target.value)}
              className="flex-1 bg-transparent text-xs font-mono text-slate-200 outline-none"
            />
          </div>
        </div>

        {/* Security Sandbox Info */}
        <div className="p-5 rounded-2xl bg-[#121520] border border-[#1F2637] space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <Shield size={14} className="text-emerald-400" />
            <span>Orchid Security Policies</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Zeno enforces strict sandboxing: destructive wipe commands (`rm -rf`, `format`) and system directory writes (`C:\Windows`) are automatically blocked. Package installations and tests are confined to dedicated project `.venv` environments.
          </p>
        </div>
      </div>
    </div>
  );
};
