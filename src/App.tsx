import React, { useState, useEffect, useRef, useMemo } from 'react';
import { marked } from 'marked';
import {
  Settings,
  X,
  Plus,
  Paperclip,
  Image as ImageIcon,
  Copy,
  ChevronRight,
  ShieldAlert,
  Search,
  Globe,
  Cpu,
  Monitor,
  Activity,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  Bot,
  MessageSquare,
  FileText,
  FileCode,
  FolderOpen,
  BrainCircuit,
  Eye,
  Check,
  Trash2,
  Zap,
  RotateCcw,
  AppWindow,
  Clipboard,
  Download,
  Maximize2,
  ShieldCheck,
  Terminal,
} from 'lucide-react';

marked.use({
  renderer: {
    link(token: any) {
      const titleAttr = token.title ? ` title="${token.title}"` : '';
      return `<a href="${token.href}" target="_blank" rel="noopener noreferrer"${titleAttr}>${token.text}</a>`;
    },
  },
});

declare global {
  interface Window {
    pywebview?: {
      api?: Record<string, (...args: any[]) => Promise<any>>;
    };
  }
}

interface AttachedItem {
  id: string;
  name: string;
  type: string;
  size: string;
  base64?: string;
  content?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tokens?: { input: number; output: number };
  timestamp: string;
  attachments?: AttachedItem[];
  planData?: {
    title: string;
    steps: string[];
    isDelegated?: boolean;
  };
  isStreaming?: boolean;
  isCompactedMemory?: boolean;
  archivedCount?: number;
  savedTokens?: number;
  archivedMessages?: Message[];
  agentScreenshots?: { name: string; path: string; base64: string; stepTitle?: string }[];
}

interface AgentTaskStep {
  text: string;
  completed: boolean;
}

interface AgentPlan {
  title: string;
  steps: AgentTaskStep[];
  currentStepIdx: number;
}

interface AgentState {
  hasTask: boolean;
  status: 'standby' | 'running' | 'completed';
  plan: AgentPlan | null;
  scratchpad: string[];
  thoughts: string[];
  workspaceFiles: { name: string; type: string; size: string }[];
  messages?: Message[];
  screenshots?: { name: string; path: string; base64: string; stepTitle?: string }[];
}

// Sleek, reusable glowing Zeno 'Z' emblem badge
const ZenoLogo = ({
  size = 20,
  glow = false,
  pulse = false,
  className = '',
}: {
  size?: number;
  glow?: boolean;
  pulse?: boolean;
  className?: string;
}) => (
  <div
    style={{ width: size, height: size, minWidth: size, minHeight: size }}
    className={`relative shrink-0 flex items-center justify-center rounded-lg bg-gradient-to-br from-[#1E3A8A] via-[#0F172A] to-[#0A0A0C] border border-[#3B82F6]/60 select-none shadow-md ${
      glow ? 'shadow-[#3B82F6]/30 shadow-lg' : ''
    } ${pulse ? 'animate-pulse' : ''} ${className}`}
  >
    <svg viewBox="0 0 24 24" fill="none" className="w-[68%] h-[68%]" stroke="currentColor">
      <path
        d="M5 6.5h14L7 17.5h12"
        stroke="url(#zeno-grad)"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient id="zeno-grad" x1="5" y1="6.5" x2="19" y2="17.5" gradientUnits="userSpaceOnUse">
          <stop stopColor="#60A5FA" />
          <stop offset="1" stopColor="#38BDF8" />
        </linearGradient>
      </defs>
    </svg>
  </div>
);

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  created_at: number;
  last_activity: number;
  flagged_for_deletion: boolean;
  hours_until_purge?: number;
  agentState?: AgentState;
}

interface ApiKeySlot {
  id: string;
  provider: string;
  key: string;
}

const PROVIDER_MODELS: Record<string, string[]> = {
  Gemini: ['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-flash'],
  'Anthropic Claude': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
  OpenRouter: ['openrouter/google/gemini-2.5-flash', 'openrouter/anthropic/claude-3.5-sonnet', 'openrouter/meta-llama/llama-3.3-70b-instruct'],
  OpenAI: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
  Groq: ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768'],
};

const MODEL_DISPLAY_LABELS: Record<string, string> = {
  'gemini-3.5-flash-lite': 'gemini-3.5-flash-lite (Cheapest - Default)',
  'gemini-3.6-flash': 'gemini-3.6-flash (Second smartest)',
  'gemini-3.8-flash': 'gemini-3.8-flash (Smartest)',
};

const PROVIDERS = Object.keys(PROVIDER_MODELS);
const THINKING_LEVELS = ['Minimal', 'Low', 'Medium', 'High'];

const CATEGORIES = [
  { id: 'system_read', name: 'system_read', desc: 'Allows reading battery, CPU, RAM, disk, uptime, and OS details.' },
  { id: 'screen_capture', name: 'screen_capture', desc: 'Allows taking screenshots of displays and browser tabs.' },
  { id: 'clipboard', name: 'clipboard', desc: 'Allows reading and writing to the system clipboard.' },
  { id: 'file_read', name: 'file_read', desc: 'Allows reading files and listing directories in user workspace.' },
  { id: 'file_write', name: 'file_write', desc: 'Allows creating and editing files in default AI project workspace.' },
  { id: 'app_launch', name: 'app_launch', desc: 'Warning: Allows launching external applications from the allowlist.' },
  { id: 'python_exec', name: 'python_exec', desc: 'Warning: Allows executing arbitrary Python code in an isolated subprocess.' },
  { id: 'web_search', name: 'web_search', desc: 'Allows searching the web for live technical documentation.' },
  { id: 'dev_tools', name: 'Development & Autonomous Tools Suite', desc: 'Grant access to development tools: pip, dev servers (start/stop/logs), git, test runner, background jobs, sandboxes.' },
];

// Helper to detect if pasted text is genuinely source code (prevents false positives on normal prose/emails)
function detectIsCode(text: string): boolean {
  if (!text || text.trim().length < 30) return false;
  const trimmed = text.trim();

  // If text is wrapped in code markdown fences, it is code
  if (/^```[a-z0-9_-]*\n[\s\S]+```$/i.test(trimmed)) return true;

  const lines = trimmed.split('\n');
  if (lines.length < 2) return false;

  // Check for common natural language conversational markers (e.g. email, letter, polite prose)
  const proseIndicators = [
    /\b(hello|hi|dear|regards|sincerely|thanks|thank you|please|could you|would you|yesterday|tomorrow|meeting|hope this helps)\b/i,
    /\b(i am|we are|you can|let me know|in order to|as discussed|attached is|feel free)\b/i,
  ];
  let proseScore = 0;
  for (const p of proseIndicators) {
    if (p.test(trimmed)) proseScore++;
  }

  // Strong programming language structural declarations
  const strongPatterns = [
    /^\s*(def|async\s+def)\s+[a-zA-Z_]\w*\s*\([^)]*\)\s*:/m,
    /^\s*(function\*?|class)\s+[a-zA-Z_]\w*/m,
    /^\s*(const|let|var)\s+[a-zA-Z_]\w*\s*[:=]/m,
    /^\s*(import\s+[\w{},* ]+\s+from\s+['"]|from\s+[\w.]+\s+import\s+[\w*, ]+)/m,
    /^\s*#include\s+<[\w.]+>/m,
    /^\s*(public|private|protected)\s+(static\s+)?(void|class|int|String|boolean)\b/m,
    /^\s*(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE)\s+[a-zA-Z_]/im,
    /<\/?(div|span|button|input|form|table|tr|td|h[1-6]|p|a|ul|li|template|script|style)[\s>]/i,
    /=>\s*\{/m,
    /\b(console\.log|print\(|fmt\.Println|System\.out\.println)\b/m,
    /^[ \t]*(if|for|while|switch)\s*\(.+\)\s*\{/m,
    /^[ \t]*(if|elif|for|while)\s+.+:\s*$/m,
  ];

  let strongMatches = 0;
  for (const pattern of strongPatterns) {
    if (pattern.test(trimmed)) strongMatches++;
  }

  const semicolons = lines.filter((l) => l.trim().endsWith(';')).length;
  const codeBraces = (trimmed.match(/[{}]/g) || []).length;

  // Disqualify if it has conversational prose markers and few strong code patterns
  if (proseScore >= 1 && strongMatches < 2) {
    return false;
  }

  // Require at least 2 strong structural code indicators, or 1 strong match plus heavy syntax density
  if (strongMatches >= 2) return true;
  if (strongMatches >= 1 && (semicolons >= 2 || codeBraces >= 4)) return true;

  // JSON object or array detection
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch {}
  }

  return false;
}

// Detect code language for pasted snippets
function detectCodeLanguage(text: string): string {
  if (/def\s+\w+|import\s+\w+|from\s+\w+\s+import|elif\s+|__init__/i.test(text)) return 'python';
  if (/interface\s+\w+|type\s+\w+\s*=|:\s*string|:\s*number|:\s*boolean/i.test(text)) return 'typescript';
  if (/function\s+\w+|const\s+\w+|let\s+\w+|console\.log/i.test(text)) return 'javascript';
  if (/<html|<div|<body|<head|<!DOCTYPE/i.test(text)) return 'html';
  if (/SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET/i.test(text)) return 'sql';
  if (/#include\s+<|std::/i.test(text)) return 'cpp';
  if (text.trim().startsWith('{') && text.trim().endsWith('}')) return 'json';
  if (text.includes('{') && (text.includes('color:') || text.includes('display:') || text.includes('margin:'))) return 'css';
  return 'code';
}

export default function App() {
  // Dual Mode: 'chat' (Desktop Assistant) vs 'agentic' (Agentic Worker)
  const [activeMode, setActiveMode] = useState<'chat' | 'agentic'>('chat');

  // Default standby agent state for fresh sessions
  const defaultAgentState: AgentState = {
    hasTask: false,
    status: 'standby',
    plan: null,
    scratchpad: [],
    thoughts: [],
    workspaceFiles: [],
    messages: [],
    screenshots: [],
  };

  // Sessions and Retention (each chat is an independent agent with its own context & files)
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    try {
      const cached = localStorage.getItem('zeno_chat_sessions');
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (_) {}
    return [
      {
        id: 'sess-1',
        title: 'Zeno Assistant Welcome',
        messages: [
          {
            id: 'welcome',
            role: 'system',
            content: 'Zeno is ready. Type a message or attach files/images to start.',
            timestamp: new Date().toLocaleTimeString(),
          },
        ],
        created_at: Date.now(),
        last_activity: Date.now(),
        flagged_for_deletion: false,
        agentState: {
          hasTask: false,
          status: 'standby',
          plan: null,
          scratchpad: [],
          thoughts: [],
          workspaceFiles: [],
        },
      },
    ];
  });
  const [activeSessionId, setActiveSessionId] = useState<string>('sess-1');
  const [searchQuery, setSearchQuery] = useState('');
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Input & Status
  const [inputText, setInputText] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedItem[]>([]);
  const [statusText, setStatusText] = useState('Ready');
  const [tokenCounts, setTokenCounts] = useState({ input: 0, output: 0 });
  const [isRunning, setIsRunning] = useState(false);
  const [currentStepText, setCurrentStepText] = useState<string>('');
  const [nextStepText, setNextStepText] = useState<string>('');

  // 3 Dynamic Provider Checklist Slots (No hardcoded keys; user selects provider and supplies key)
  const [apiKeySlots, setApiKeySlots] = useState<ApiKeySlot[]>(() => {
    try {
      const saved = localStorage.getItem('zeno_api_key_slots');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return [
      { id: 'slot-1', provider: 'Gemini', key: '' },
      { id: 'slot-2', provider: 'Anthropic Claude', key: '' },
      { id: 'slot-3', provider: 'OpenRouter', key: '' },
    ];
  });

  // Model & Reasoning In-Chat Controls (gemini-3.5-flash-lite cheapest default)
  const [activeModel, setActiveModel] = useState<string>(() => {
    try {
      return localStorage.getItem('zeno_active_model') || 'gemini-3.5-flash-lite';
    } catch {
      return 'gemini-3.5-flash-lite';
    }
  });
  const [thinkingLevel, setThinkingLevel] = useState('Medium');
  const [autoSwitch, setAutoSwitch] = useState(true);
  const [defaultWorkspace, setDefaultWorkspace] = useState('~/Documents/ZenoWorkspace');
  const [autoApproveSafe, setAutoApproveSafe] = useState(true);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [settingsSavedNotice, setSettingsSavedNotice] = useState('');

  // Context Compaction State
  const [isCompacting, setIsCompacting] = useState(false);
  const [compactToast, setCompactToast] = useState('');
  const [expandedMemoryIds, setExpandedMemoryIds] = useState<Set<string>>(new Set());
  const [archivedModalMessages, setArchivedModalMessages] = useState<Message[] | null>(null);
  const [dismissedCompactNoticeId, setDismissedCompactNoticeId] = useState<string>('');

  // Permissions state
  const [permissions, setPermissions] = useState<Record<string, boolean>>({
    system_read: false,
    screen_capture: false,
    clipboard: false,
    file_read: false,
    file_write: false,
    app_launch: false,
    python_exec: false,
    web_search: true,
    dev_tools: false,
  });
  const [askedCategories, setAskedCategories] = useState<Record<string, boolean>>({});

  // Zeno Observer & Autonomous Safety State
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [activeJobs, setActiveJobs] = useState<any[]>([]);
  const [observerDialogues, setObserverDialogues] = useState<any[]>([]);
  const [rightColTab, setRightColTab] = useState<'files' | 'observer' | 'jobs'>('files');

  const refreshSafetyData = async () => {
    if (window.pywebview?.api) {
      try {
        if (window.pywebview.api.get_pending_approvals) {
          const apps = await window.pywebview.api.get_pending_approvals();
          setPendingApprovals(Array.isArray(apps) ? apps : []);
        }
        if (window.pywebview.api.get_active_jobs) {
          const jbs = await window.pywebview.api.get_active_jobs();
          setActiveJobs(Array.isArray(jbs) ? jbs : []);
        }
        if (window.pywebview.api.get_observer_dialogues) {
          const dls = await window.pywebview.api.get_observer_dialogues(25);
          setObserverDialogues(Array.isArray(dls) ? dls : []);
        }
      } catch {}
    }
  };

  const handleDecideApproval = async (approvalId: string, approved: boolean) => {
    if (window.pywebview?.api?.decide_approval) {
      await window.pywebview.api.decide_approval({ approval_id: approvalId, approved });
      await refreshSafetyData();
    }
  };

  const handleCancelJob = async (jobId: string) => {
    if (window.pywebview?.api?.cancel_background_job) {
      await window.pywebview.api.cancel_background_job({ job_id: jobId });
      await refreshSafetyData();
    }
  };

  // Modals
  const [pendingPermission, setPendingPermission] = useState<{
    category: string;
    description: string;
    resolve: (allowed: boolean) => void;
  } | null>(null);

  const [pendingHumanReview, setPendingHumanReview] = useState<{
    code: string;
    reason: string;
    resolve: (approved: boolean) => void;
  } | null>(null);

  const [screenTargetPicker, setScreenTargetPicker] = useState<{
    isOpen: boolean;
    resolve: (target: string) => void;
  } | null>(null);

  // Active session and independent agent state
  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];
  const activeAgentState: AgentState = activeSession?.agentState || defaultAgentState;

  // Session-isolated agent state updater
  const updateSessionAgent = (sessionId: string, updater: (prev: AgentState) => AgentState) => {
    setSessions((prev) => {
      const updated = prev.map((s) => {
        if (s.id === sessionId) {
          const current = s.agentState || { ...defaultAgentState };
          return {
            ...s,
            agentState: updater(current),
            last_activity: Date.now(),
          };
        }
        return s;
      });
      if (window.pywebview?.api?.save_chats) {
        window.pywebview.api.save_chats(updated);
      }
      return updated;
    });
  };

  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Memory & Personalization states
  const [memoryText, setMemoryText] = useState<string>('');
  const [importNotes, setImportNotes] = useState<string>('');
  const [isImportingMemory, setIsImportingMemory] = useState<boolean>(false);
  const [isSavingMemory, setIsSavingMemory] = useState<boolean>(false);
  const [memoryNotice, setMemoryNotice] = useState<string>('');

  // Drop-Up '+' Menu & File Inputs
  const [isPlusMenuOpen, setIsPlusMenuOpen] = useState<boolean>(false);
  const plusMenuRef = useRef<HTMLDivElement>(null);
  const docFileInputRef = useRef<HTMLInputElement>(null);
  const imageFileInputRef = useRef<HTMLInputElement>(null);

  // Live Screen & Tab Target Picker Modal
  const [isTargetPickerOpen, setIsTargetPickerOpen] = useState<boolean>(false);
  const [targetSearchQuery, setTargetSearchQuery] = useState<string>('');
  const [liveScreenTargets, setLiveScreenTargets] = useState<any[]>([]);
  const [isCapturingScreen, setIsCapturingScreen] = useState<boolean>(false);

  // Zoom Lightbox
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);

  // Calculate Available Models Strictly based on Provided Keys
  const availableModels = useMemo(() => {
    const models: string[] = [];
    apiKeySlots.forEach((slot) => {
      if (slot.key && slot.key.trim().length > 0) {
        const modelsForProv = PROVIDER_MODELS[slot.provider] || [];
        modelsForProv.forEach((m) => {
          if (!models.includes(m)) models.push(m);
        });
      }
    });
    return models;
  }, [apiKeySlots]);

  // Ensure activeModel is valid when availableModels changes
  useEffect(() => {
    if (availableModels.length > 0) {
      if (!activeModel || !availableModels.includes(activeModel)) {
        setActiveModel(availableModels[0]);
      }
    }
  }, [availableModels]);

  // Persist selected model to localStorage whenever changed
  useEffect(() => {
    if (activeModel) {
      try {
        localStorage.setItem('zeno_active_model', activeModel);
      } catch {}
    }
  }, [activeModel]);

  // Auto-persist all conversation sessions and messages whenever sessions change
  useEffect(() => {
    if (!sessions || sessions.length === 0) return;
    try {
      localStorage.setItem('zeno_chat_sessions', JSON.stringify(sessions));
    } catch (_) {}

    if (window.pywebview?.api?.save_chats) {
      window.pywebview.api.save_chats(sessions);
    }
  }, [sessions]);

  // Scroll to bottom on updates
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages, statusText, currentStepText]);

  // Connect and initialize pywebview desktop API bridge
  // Uses pywebviewready event + a retry loop to handle the startup race condition
  // where window.pywebview exists but its API methods aren't callable yet.
  useEffect(() => {
    let didInit = false;

    const initDesktopBridge = async () => {
      if (didInit) return;

      // Retry up to 20 times with 150ms gaps (3s total) waiting for API to be ready
      for (let attempt = 0; attempt < 20; attempt++) {
        const api = window.pywebview?.api;
        if (api && typeof api.get_settings === 'function') {
          didInit = true;
          try {
            if (api.get_permissions) {
              const storedPerms = await api.get_permissions();
              if (storedPerms && typeof storedPerms === 'object') {
                setPermissions((prev) => ({ ...prev, ...storedPerms }));
              }
            }
            if (api.get_settings) {
              const st = await api.get_settings();
              if (st) {
                if (st.defaultWorkspace) setDefaultWorkspace(st.defaultWorkspace);
                if (typeof st.autoApproveSafe === 'boolean') setAutoApproveSafe(st.autoApproveSafe);
                if (typeof st.autoSwitch === 'boolean') setAutoSwitch(st.autoSwitch);
                if (st.thinkingLevel) setThinkingLevel(st.thinkingLevel);
                if (st.keys) {
                  setApiKeySlots((prev) =>
                    prev.map((slot) => {
                      const foundKey = st.keys[slot.provider];
                      return foundKey ? { ...slot, key: foundKey } : slot;
                    })
                  );
                }
              }
            }
            if (api.get_memory) {
              const mem = await api.get_memory();
              if (mem) setMemoryText(mem);
            }
            if (api.load_chats) {
              const storedChats = await api.load_chats();
              if (Array.isArray(storedChats) && storedChats.length > 0) {
                setSessions(storedChats);
                setActiveSessionId((prev) => {
                  const exists = storedChats.some((s) => s.id === prev);
                  return exists ? prev : storedChats[0].id;
                });
              } else if (sessions && sessions.length > 0) {
                await api.save_chats(sessions);
              }
            }
          } catch (err) {
            console.warn('Desktop bridge init error:', err);
          }
          return;
        }
        await new Promise((r) => setTimeout(r, 150));
      }

      // Web/fetch fallback for memory
      try {
        const mRes = await fetch('/api/memory');
        if (mRes.ok) {
          const mData = await mRes.json();
          if (mData.memory) setMemoryText(mData.memory);
        }
      } catch (_) {}
    };

    // Always listen for pywebviewready (fires when the API is guaranteed ready)
    window.addEventListener('pywebviewready', initDesktopBridge);
    // Also try immediately in case pywebviewready already fired before this effect ran
    initDesktopBridge();

    return () => window.removeEventListener('pywebviewready', initDesktopBridge);
  }, []);

  // Periodic safety polling for human approvals, observer interventions, and jobs
  useEffect(() => {
    refreshSafetyData();
    const interval = setInterval(refreshSafetyData, 4000);
    return () => clearInterval(interval);
  }, []);

  // Close plus menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target as Node)) {
        setIsPlusMenuOpen(false);
      }
    };
    if (isPlusMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isPlusMenuOpen]);

  // Neural Particle Canvas Animation
  useEffect(() => {
    if (activeMode !== 'agentic' || !activeAgentState.hasTask || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    const width = (canvas.width = canvas.offsetWidth);
    const height = (canvas.height = canvas.offsetHeight);

    const particles: { x: number; y: number; vx: number; vy: number; radius: number }[] = [];
    const numParticles = 24;

    for (let i = 0; i < numParticles; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.8,
        radius: Math.random() * 2 + 1.5,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw connecting lines between close particles
      for (let i = 0; i < numParticles; i++) {
        for (let j = i + 1; j < numParticles; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 110) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(59, 130, 246, ${1 - dist / 110 * 0.85})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      // Draw and update particles
      particles.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#3B82F6';
        ctx.shadowColor = '#3B82F6';
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;

        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animationFrameId);
  }, [activeMode, activeAgentState.hasTask]);

  // Handle Copy
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  // Generate Topic from user query
  const generateTopic = (text: string): string => {
    const l = text.toLowerCase();
    if (l.includes('battery') || l.includes('system') || l.includes('cpu')) return 'System Diagnostics & Battery';
    if (l.includes('screen') || l.includes('capture') || l.includes('tab')) return 'Display & Browser Capture';
    if (l.includes('summary') && l.includes('downloads')) return 'Downloads Document Synthesis';
    if (l.includes('python') || l.includes('code')) return 'Python Script Execution';
    if (l.includes('search') || l.includes('web')) return 'Technical Web Search';
    if (l.includes('project') || l.includes('workspace')) return 'Project Workspace Builder';
    return text.slice(0, 24).replace(/\n/g, ' ');
  };

  // Permission Request Modal Hook
  const checkPermission = async (category: string, description: string): Promise<boolean> => {
    if (permissions[category] === true) return true;
    if (askedCategories[category] && permissions[category] === false) return false;

    return new Promise<boolean>((resolve) => {
      setPendingPermission({
        category,
        description,
        resolve: (allowed: boolean) => {
          setPermissions((prev) => ({ ...prev, [category]: allowed }));
          setAskedCategories((prev) => ({ ...prev, [category]: true }));
          setPendingPermission(null);
          resolve(allowed);
        },
      });
    });
  };

  // Human Safety Review Escalation Modal
  const requestHumanReview = async (code: string, reason: string): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      setPendingHumanReview({
        code,
        reason,
        resolve: (approved: boolean) => {
          setPendingHumanReview(null);
          resolve(approved);
        },
      });
    });
  };

  // Target Screen Picker Modal
  const requestScreenTarget = async (): Promise<string> => {
    return new Promise<string>((resolve) => {
      setScreenTargetPicker({
        isOpen: true,
        resolve: (target: string) => {
          setScreenTargetPicker(null);
          resolve(target);
        },
      });
    });
  };

  // File Attachment Handling (Documents, Code, Images)
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      const isImg = file.type.startsWith('image/');

      if (isImg) {
        reader.onload = (event) => {
          const base64 = event.target?.result as string;
          setAttachedFiles((prev) => [
            ...prev,
            {
              id: `att-${Date.now()}-${file.name}`,
              name: file.name,
              type: file.type,
              size: `${Math.round(file.size / 1024)} KB`,
              base64,
            },
          ]);
        };
        reader.readAsDataURL(file);
      } else {
        reader.onload = (event) => {
          const content = event.target?.result as string;
          const isCodeFile = detectIsCode(content) || file.name.match(/\.(py|ts|tsx|js|jsx|json|html|css|cpp|c|rs|go|sql)$/i);
          setAttachedFiles((prev) => [
            ...prev,
            {
              id: `att-${Date.now()}-${file.name}`,
              name: file.name,
              type: isCodeFile ? 'text/code' : (file.type || 'text/plain'),
              size: `${Math.round(file.size / 1024)} KB`,
              content,
            },
          ]);
        };
        reader.readAsText(file);
      }
    });

    if (e.target) e.target.value = '';
  };

  const removeAttachment = (id: string) => {
    setAttachedFiles((prev) => prev.filter((a) => a.id !== id));
  };

  // Memory & Personalization Handlers
  const handleSaveMemoryDirect = async () => {
    setIsSavingMemory(true);
    try {
      if (window.pywebview?.api?.save_memory) {
        await window.pywebview.api.save_memory(memoryText);
      } else {
        await fetch('/api/memory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: memoryText }),
        });
      }
      setMemoryNotice('Memory saved successfully!');
      setTimeout(() => setMemoryNotice(''), 3000);
    } catch (err: any) {
      setMemoryNotice(`Error: ${err.message}`);
    } finally {
      setIsSavingMemory(false);
    }
  };

  const handleClearMemory = async () => {
    if (!confirm('Reset memory back to default profile?')) return;
    try {
      if (window.pywebview?.api?.clear_memory) {
        await window.pywebview.api.clear_memory();
        const updated = await window.pywebview.api.get_memory();
        setMemoryText(updated);
      } else {
        const res = await fetch('/api/memory');
        const data = await res.json();
        setMemoryText(data.memory || '');
      }
      setMemoryNotice('Memory reset to default.');
      setTimeout(() => setMemoryNotice(''), 3000);
    } catch (_) {}
  };

  const handleImportMemoryAI = async () => {
    if (!importNotes.trim()) return;
    setIsImportingMemory(true);
    setMemoryNotice('Synthesizing memories with AI...');
    const primaryKey = apiKeySlots.find((s) => s.key.trim().length > 0)?.key || '';

    try {
      let updatedMem = '';
      if (window.pywebview?.api?.import_memory_ai) {
        const res = await window.pywebview.api.import_memory_ai({
          notes: importNotes,
          model: activeModel,
          customApiKey: primaryKey,
        });
        if (res && res.memory) updatedMem = res.memory;
      } else {
        const res = await fetch('/api/memory/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            notes: importNotes,
            model: activeModel,
            customApiKey: primaryKey,
          }),
        });
        const data = await res.json();
        if (data && data.memory) updatedMem = data.memory;
      }
      if (updatedMem) {
        setMemoryText(updatedMem);
        setImportNotes('');
        setMemoryNotice('Memories synthesized & saved!');
      } else {
        setMemoryNotice('Memory updated.');
      }
      setTimeout(() => setMemoryNotice(''), 4000);
    } catch (err: any) {
      setMemoryNotice(`Synthesis failed: ${err.message}`);
    } finally {
      setIsImportingMemory(false);
    }
  };

  // Open Live Window & Browser Tab Screenshot Picker Modal
  const handleOpenTargetPicker = async () => {
    setIsTargetPickerOpen(true);
    setTargetSearchQuery('');
    try {
      let targets: any[] = [];
      if (window.pywebview?.api?.list_screen_targets) {
        targets = await window.pywebview.api.list_screen_targets();
      } else {
        targets = [
          { id: 'all', name: 'All Monitors Combined', description: 'Full desktop canvas', type: 'display' },
          { id: 'monitor_1', name: 'Primary Display', description: 'Main physical screen', type: 'display' },
          { id: 'browser_tab', name: 'Active Browser Tab', description: 'Active web browser window and tab bar', type: 'browser_tab' },
          { id: 'active_window', name: 'Focused Application Window', description: 'Active foreground window', type: 'app_window' },
        ];
      }
      setLiveScreenTargets(targets);
    } catch (_) {}
  };

  // Capture Target without auto-sending (attaches preview chip to input bar)
  const handleCaptureSelectedTarget = async (targetId: string, targetName: string) => {
    setIsCapturingScreen(true);
    try {
      let fileItem: AttachedItem | null = null;
      if (window.pywebview?.api?.capture_screen) {
        const res = await window.pywebview.api.capture_screen(targetId);
        if (res && res.base64) {
          fileItem = {
            id: `scr-${Date.now()}`,
            name: res.name || `${targetName}.png`,
            type: res.type || 'image/png',
            size: res.size || '120 KB',
            base64: res.base64,
          };
        }
      }
      if (!fileItem) {
        fileItem = {
          id: `scr-${Date.now()}`,
          name: `${targetName.replace(/\s+/g, '_').slice(0, 24)}.png`,
          type: 'image/png',
          size: '115 KB',
          base64: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzkUv1EAAAAABJRU5ErkJggg==',
        };
      }
      setAttachedFiles((prev) => [...prev, fileItem!]);
      setIsTargetPickerOpen(false);
    } catch (err: any) {
      console.warn('Capture error:', err);
    } finally {
      setIsCapturingScreen(false);
    }
  };

  // Smart Code & Image Paste Detection in Input Box (Claude style)
  const handleInputPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const clipboardData = e.clipboardData;
    if (!clipboardData) return;

    // 1. Check for pasted image
    if (clipboardData.items) {
      for (let i = 0; i < clipboardData.items.length; i++) {
        const item = clipboardData.items[i];
        if (item.type.indexOf('image') !== -1) {
          const file = item.getAsFile();
          if (file) {
            e.preventDefault();
            const reader = new FileReader();
            reader.onload = (event) => {
              const base64 = event.target?.result as string;
              setAttachedFiles((prev) => [
                ...prev,
                {
                  id: `clip-img-${Date.now()}`,
                  name: `pasted_image_${Date.now()}.png`,
                  type: file.type,
                  size: `${Math.round(file.size / 1024)} KB`,
                  base64,
                },
              ]);
            };
            reader.readAsDataURL(file);
            return;
          }
        }
      }
    }

    // 2. Check for pasted code
    const text = clipboardData.getData('text');
    if (text && text.length > 25 && detectIsCode(text)) {
      e.preventDefault();
      const lang = detectCodeLanguage(text);
      const lines = text.split('\n').length;
      setAttachedFiles((prev) => [
        ...prev,
        {
          id: `code-${Date.now()}`,
          name: `Snippet (${lang})`,
          type: 'text/code',
          size: `${lines} lines`,
          content: text,
        },
      ]);
    }
  };

  // Paste from System Clipboard via Drop-up Menu
  const handlePasteFromClipboard = async () => {
    try {
      let clipText = '';
      if (window.pywebview?.api?.read_clipboard) {
        clipText = await window.pywebview.api.read_clipboard();
      } else {
        clipText = await navigator.clipboard.readText();
      }
      if (clipText && clipText.trim()) {
        if (detectIsCode(clipText)) {
          const lang = detectCodeLanguage(clipText);
          setAttachedFiles((prev) => [
            ...prev,
            {
              id: `clip-code-${Date.now()}`,
              name: `Snippet (${lang})`,
              type: 'text/code',
              size: `${clipText.split('\n').length} lines`,
              content: clipText,
            },
          ]);
        } else {
          setAttachedFiles((prev) => [
            ...prev,
            {
              id: `clip-txt-${Date.now()}`,
              name: `Clipboard Note`,
              type: 'text/plain',
              size: `${clipText.length} chars`,
              content: clipText,
            },
          ]);
        }
      }
    } catch (err) {
      console.warn('Clipboard read error:', err);
    }
  };

  // Retry / Regenerate Turn
  const handleRetryTurn = async (targetMsg: Message) => {
    if (isRunning) return;
    if (targetMsg.role === 'user') {
      const prompt = targetMsg.content;
      const atts = targetMsg.attachments || [];
      const msgIdx = activeSession.messages.findIndex((m) => m.id === targetMsg.id);
      if (msgIdx !== -1) {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId
              ? { ...s, messages: s.messages.slice(0, msgIdx) }
              : s
          )
        );
      }
      executeTurn(prompt, atts);
    } else if (targetMsg.role === 'assistant') {
      const msgIdx = activeSession.messages.findIndex((m) => m.id === targetMsg.id);
      if (msgIdx > 0) {
        const prevUser = activeSession.messages
          .slice(0, msgIdx)
          .reverse()
          .find((m) => m.role === 'user');
        if (prevUser) {
          const prompt = prevUser.content;
          const atts = prevUser.attachments || [];
          setSessions((prev) =>
            prev.map((s) =>
              s.id === activeSessionId
                ? { ...s, messages: s.messages.slice(0, msgIdx) }
                : s
            )
          );
          executeTurn(prompt, atts);
        }
      }
    }
  };

  // Unflag chat
  const handleUnflagChat = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, flagged_for_deletion: false, last_activity: Date.now() } : s))
    );
  };

  // Manually delete a chat conversation
  const handleDeleteChat = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (sessions.length <= 1) {
      const freshSession: ChatSession = {
        id: 'session-' + Date.now(),
        title: 'New Conversation',
        messages: [],
        created_at: Date.now(),
        last_activity: Date.now(),
        flagged_for_deletion: false,
        agentState: { ...defaultAgentState },
      };
      setActiveSessionId(freshSession.id);
      setSessions([freshSession]);
      if (window.pywebview?.api?.delete_chat) {
        window.pywebview.api.delete_chat(sessionId);
      }
      if (window.pywebview?.api?.save_chats) {
        window.pywebview.api.save_chats([freshSession]);
      }
      return;
    }
    const remaining = sessions.filter((s) => s.id !== sessionId);
    if (activeSessionId === sessionId && remaining.length > 0) {
      setActiveSessionId(remaining[0].id);
    }
    setSessions(remaining);
    if (window.pywebview?.api?.delete_chat) {
      window.pywebview.api.delete_chat(sessionId);
    } else if (window.pywebview?.api?.save_chats) {
      window.pywebview.api.save_chats(remaining);
    }
  };

  // Delegate Plan to Agentic Worker -- sends the plan as a real prompt to the AI agent
  const handleDelegatePlan = (plan: { title: string; steps: string[] }) => {
    setActiveMode('agentic');

    // Mark plan as delegated in chat
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messages: s.messages.map((m) =>
              m.planData ? { ...m, planData: { ...m.planData, isDelegated: true } } : m
            ),
          };
        }
        return s;
      })
    );

    // Build a clear instruction from the plan steps and execute through the real agent
    const agentPrompt = `Execute the following plan step by step. Use the available tools (write_file, run_python, create_project_workspace, etc.) to actually create the files, write the code, and complete each step.\n\nPlan: ${plan.title}\n\n${plan.steps.map((st, i) => `${i + 1}. ${st}`).join('\n')}\n\nExecute all steps now. Create real files with real content.`;
    executeTurn(agentPrompt);
  };

  // Launch fresh agentic task directly from Standby UI
  const launchAgenticTask = (taskTitle: string, taskInput: string | string[]) => {
    setActiveMode('agentic');
    const prompt = Array.isArray(taskInput)
      ? `Task: ${taskTitle}\nExecute the following steps using available tools:\n${taskInput.map((st, i) => `${i + 1}. ${st}`).join('\n')}`
      : taskInput;
    executeTurn(prompt);
  };

  // Streaming Text Animator for smooth response rendering
  const streamAssistantResponse = async (fullText: string, planData?: { title: string; steps: string[] }) => {
    const msgId = `a-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString();

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messages: [
              ...s.messages,
              {
                id: msgId,
                role: 'assistant',
                content: '',
                timestamp,
                planData,
                isStreaming: true,
              },
            ],
          };
        }
        return s;
      })
    );

    const words = fullText.split(' ');
    let currentStream = '';
    for (let i = 0; i < words.length; i++) {
      currentStream += (i === 0 ? '' : ' ') + words[i];
      if (i % 3 === 0 || i === words.length - 1) {
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === activeSessionId) {
              return {
                ...s,
                messages: s.messages.map((m) => (m.id === msgId ? { ...m, content: currentStream, isStreaming: true } : m)),
              };
            }
            return s;
          })
        );
        await new Promise((r) => setTimeout(r, 18));
      }
    }

    // Agent is done returning messages: mark isStreaming: false to trigger rich Markdown formatting
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messages: s.messages.map((m) =>
              m.id === msgId ? { ...m, content: fullText, isStreaming: false } : m
            ),
          };
        }
        return s;
      })
    );
  };

  // Core Turn Execution
  const executeTurn = async (rawInput?: string | string[], overrideAttachments?: AttachedItem[]) => {
    const userText = Array.isArray(rawInput)
      ? rawInput.join('\n')
      : typeof rawInput === 'string'
      ? rawInput
      : inputText;
    const currentAttachments = overrideAttachments ? [...overrideAttachments] : [...attachedFiles];
    if ((!userText || !userText.trim()) && currentAttachments.length === 0) return;
    if (isRunning) return;

    // Check if API key is configured
    if (availableModels.length === 0) {
      const missingKeyMsg: Message = {
        id: `sys-${Date.now()}`,
        role: 'system',
        content:
          'API key missing. Open Settings and add your API key after choosing your provider (Gemini, Claude, OpenRouter, OpenAI, Groq). Zeno does not work without an API key.',
        timestamp: new Date().toLocaleTimeString(),
      };
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSessionId ? { ...s, messages: [...s.messages, missingKeyMsg] } : s))
      );
      setIsSettingsOpen(true);
      return;
    }

    setAttachedFiles([]);
    setInputText('');
    setIsRunning(true);
    setStatusText('Thinking...');
    setCurrentStepText('Analyzing intent & attached context');
    setNextStepText('Formulating tool execution plan');

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString(),
      attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
    };

    if (activeMode !== 'agentic') {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSessionId) {
            const updatedTitle = s.title === 'Zeno Assistant Welcome' || s.title === 'New Conversation'
              ? generateTopic(userText || currentAttachments[0]?.name || 'Attached Content')
              : s.title;
            return {
              ...s,
              title: updatedTitle,
              last_activity: Date.now(),
              flagged_for_deletion: false,
              messages: [...s.messages, userMsg],
            };
          }
          return s;
        })
      );
    }

    // If inside Agentic Worker mode, create a plan first, then execute steps one by one
    if (activeMode === 'agentic') {
      const primaryKey = apiKeySlots.find((s) => s.key.trim().length > 0)?.key || '';

      // PHASE 1: Generate a detailed step-by-step plan
      updateSessionAgent(activeSessionId, (st) => ({
        ...st,
        hasTask: true,
        status: 'running',
        messages: [...(st.messages || []), userMsg],
        plan: {
          title: 'Creating execution plan...',
          steps: [{ text: 'Analyzing task and generating plan...', completed: false }],
          currentStepIdx: 0,
        },
        scratchpad: [`Task received: ${userText.slice(0, 100)}`],
        thoughts: ['Analyzing task requirements...', 'Generating step-by-step execution plan...'],
        workspaceFiles: [],
      }));

      setCurrentStepText('Creating detailed execution plan...');
      setNextStepText('Breaking down task into actionable steps');

      try {
        // Ask backend to generate a plan
        let planData: { title: string; steps: string[] } | null = null;
        if (window.pywebview?.api?.create_agent_plan) {
          planData = await window.pywebview.api.create_agent_plan({
            task: userText,
            model: activeModel,
            customApiKey: primaryKey,
          });
        }
        if (!planData || !planData.steps || planData.steps.length === 0) {
          planData = {
            title: generateTopic(userText || 'Agentic Task'),
            steps: [
              'Phase 1: Environment Discovery & Repository Architecture Analysis',
              'Phase 2: Comprehensive Specification & Interface Contract Design',
              'Phase 3: Core Data Schemas, Type Definitions & Storage Layer',
              'Phase 4: Primary Business Logic & Domain Engine Implementation',
              'Phase 5: Auxiliary Utilities, Validation Rules & Input Handlers',
              'Phase 6: Interactive Command Parser & Error Handling Subsystems',
              'Phase 7: Comprehensive Automated Unit Test Suite Authoring',
              'Phase 8: Edge-Case & Boundary Verification Test Fixtures',
              'Phase 9: End-to-End Test Suite Execution via run_tests',
              'Phase 10: Production Hardening, Linting & Executive Audit Report',
            ],
          };
        }

        const taskTitle = planData.title;
        const planSteps = planData.steps;

        // Show plan in the UI before executing
        const agentPlanSteps: AgentTaskStep[] = planSteps.map((step) => ({
          text: step,
          completed: false,
        }));

        const planMsg: Message = {
          id: `plan-${Date.now()}`,
          role: 'system' as const,
          content: `### Execution Plan: ${taskTitle}\n\n${planSteps.map((s, i) => `${i + 1}. ${s}`).join('\n')}`,
          timestamp: new Date().toLocaleTimeString(),
        };

        updateSessionAgent(activeSessionId, (st) => ({
          ...st,
          messages: [...(st.messages || []), planMsg],
          plan: {
            title: taskTitle,
            steps: agentPlanSteps,
            currentStepIdx: 0,
          },
          thoughts: [`Plan created: "${taskTitle}" with ${planSteps.length} steps`, ...planSteps.map((s, i) => `Step ${i + 1}: ${s}`)],
          scratchpad: [`Plan: ${taskTitle}`, ...planSteps.map((s, i) => `${i + 1}. ${s}`)],
        }));

        // PHASE 2: Execute each step sequentially
        let allToolActions: string[] = [];
        let totalInTokens = 0;
        let totalOutTokens = 0;

        for (let stepIdx = 0; stepIdx < planSteps.length; stepIdx++) {
          const stepText = planSteps[stepIdx];

          // Update UI to show which step is executing
          updateSessionAgent(activeSessionId, (st) => ({
            ...st,
            plan: {
              ...st.plan!,
              currentStepIdx: stepIdx,
            },
            thoughts: [`Executing Step ${stepIdx + 1}/${planSteps.length}: ${stepText}`, ...st.thoughts.slice(0, 4)],
          }));

          setCurrentStepText(`Step ${stepIdx + 1}/${planSteps.length}: ${stepText}`);
          setNextStepText(stepIdx + 1 < planSteps.length ? `Next: ${planSteps[stepIdx + 1]}` : 'Finalizing results...');

          let stepData: any;
          if (window.pywebview?.api?.run_agent_task) {
            stepData = await window.pywebview.api.run_agent_task({
              message: userText,
              currentStep: stepText,
              planTitle: taskTitle,
              stepIndex: stepIdx,
              totalSteps: planSteps.length,
              history: (activeAgentState.messages || []).map((m) => ({
                role: m.role === 'user' ? 'user' : 'assistant',
                content: m.content,
              })),
              model: activeModel,
              customApiKey: primaryKey,
            });
          } else {
            // Fallback: use standard chat endpoint
            const res = await fetch('/api/chat', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                message: `${userText}\n\nCurrently executing step ${stepIdx + 1}: ${stepText}`,
                history: (activeAgentState.messages || []).map((m) => ({
                  role: m.role === 'user' ? 'user' : 'assistant',
                  content: m.content,
                })),
                model: activeModel,
                thinkingLevel,
                customApiKey: primaryKey,
                mode: 'agentic',
              }),
            });
            stepData = await res.json();
          }

          // Collect tool actions from this step
          const stepToolActions: string[] = stepData.toolActions || [];
          allToolActions = [...allToolActions, ...stepToolActions];
          totalInTokens += stepData.inputTokens || 0;
          totalOutTokens += stepData.outputTokens || 0;

          const newStepMsgs: Message[] = [];
          if (stepToolActions.length > 0) {
            stepToolActions.forEach((action: string, idx: number) => {
              newStepMsgs.push({
                id: `t-${Date.now()}-${stepIdx}-${idx}`,
                role: 'tool' as const,
                content: `[Step ${stepIdx + 1}] ${action}`,
                timestamp: new Date().toLocaleTimeString(),
              });
            });
          }

          const stepScreenshots = (stepData.screenshots || []).map((s: any) => ({
            ...s,
            stepTitle: `Step ${stepIdx + 1}: ${stepText}`,
          }));

          if (stepData.reply) {
            newStepMsgs.push({
              id: `astep-${Date.now()}-${stepIdx}`,
              role: 'assistant' as const,
              content: `**Step ${stepIdx + 1}: ${stepText}**\n\n${stepData.reply}`,
              timestamp: new Date().toLocaleTimeString(),
              agentScreenshots: stepScreenshots.length > 0 ? stepScreenshots : undefined,
            });
          }

          // Mark this step as completed in the plan and store messages in agent thread
          updateSessionAgent(activeSessionId, (st) => {
            const updatedSteps = st.plan!.steps.map((s, i) =>
              i === stepIdx ? { ...s, completed: true } : s
            );
            return {
              ...st,
              messages: [...(st.messages || []), ...newStepMsgs],
              plan: { ...st.plan!, steps: updatedSteps, currentStepIdx: stepIdx + 1 },
              scratchpad: [
                `Step ${stepIdx + 1} completed: ${stepText}`,
                ...stepToolActions.slice(0, 3),
                ...st.scratchpad.slice(0, 3),
              ],
              screenshots: [...(st.screenshots || []), ...stepScreenshots],
            };
          });

          if (stepData.error === 'API_KEY_MISSING') {
            setIsSettingsOpen(true);
            break;
          }
        }

        // Refresh workspace files from actual filesystem
        if (window.pywebview?.api?.list_directory) {
          try {
            const files = await window.pywebview.api.list_directory(defaultWorkspace);
            if (Array.isArray(files) && files.length > 0 && !files[0]?.error) {
              const wsFiles = files.slice(0, 12).map((f: any) => ({
                name: f.name,
                type: f.name.endsWith('.py') ? 'code'
                  : f.name.endsWith('.docx') || f.name.endsWith('.md') || f.name.endsWith('.txt') ? 'doc'
                  : f.name.endsWith('.png') || f.name.endsWith('.jpg') ? 'image'
                  : f.type === 'directory' ? 'folder'
                  : 'data',
                size: f.size_bytes ? `${Math.round(f.size_bytes / 1024)} KB` : (f.type === 'directory' ? 'dir' : '0 KB'),
              }));
              updateSessionAgent(activeSessionId, (st) => ({
                ...st,
                workspaceFiles: wsFiles,
              }));
            }
          } catch (_) {}
        }

        setTokenCounts({ input: totalInTokens, output: totalOutTokens });

        // Mark agent as completed
        updateSessionAgent(activeSessionId, (st) => ({
          ...st,
          status: 'completed',
          thoughts: [`All ${planSteps.length} steps completed for "${taskTitle}"`, ...st.thoughts.slice(0, 4)],
        }));

      } catch (err: any) {
        const errorMsg: Message = {
          id: `aerr-${Date.now()}`,
          role: 'assistant' as const,
          content: `Agent error: ${err.message}`,
          timestamp: new Date().toLocaleTimeString(),
        };
        updateSessionAgent(activeSessionId, (st) => ({
          ...st,
          status: 'completed',
          messages: [...(st.messages || []), errorMsg],
          thoughts: [`Error: ${err.message}`, ...st.thoughts],
        }));
      } finally {
        setIsRunning(false);
        setStatusText('Ready');
        setCurrentStepText('');
        setNextStepText('');
      }
      return;
    }

    const lower = userText.toLowerCase().trim();

    // 1. Precision Telemetry & Hardware Queries (Fixes laptop spec dump bug)
    const isFullSystemDiagnostic =
      lower === '/sys' ||
      lower === '/sysinfo' ||
      lower === '/telemetry' ||
      lower === '/system-status' ||
      lower === 'system info' ||
      lower === 'system status' ||
      lower === 'hardware specs' ||
      lower === 'system specs' ||
      lower === 'full specs' ||
      lower === 'all system specs';

    const isSpecificBatteryQuery =
      (lower.includes('battery') || lower.includes('power remaining') || lower === 'battery') &&
      !lower.includes('cpu') && !lower.includes('ram') && !lower.includes('disk') && !isFullSystemDiagnostic;

    const isSpecificCpuQuery =
      (lower.includes('cpu') || lower.includes('processor utilization')) &&
      !lower.includes('battery') && !lower.includes('ram') && !lower.includes('disk') && !isFullSystemDiagnostic;

    const isSpecificRamQuery =
      (lower.includes('ram') || lower.includes('memory usage')) &&
      !lower.includes('battery') && !lower.includes('cpu') && !isFullSystemDiagnostic;

    const isExplicitTelemetry = isFullSystemDiagnostic || isSpecificBatteryQuery || isSpecificCpuQuery || isSpecificRamQuery;

    if (isExplicitTelemetry) {
      const allowed = await checkPermission('system_read', 'Allows reading battery, CPU, RAM, disk, uptime, and OS details.');
      if (!allowed) {
        postToolAndReply('system_info', 'Permission denied for system_read. Turn it on in Settings.', 'Permission denied for system_read. Turn it on in Settings.');
        setIsRunning(false);
        setStatusText('Ready');
        return;
      }

      try {
        let data: any;
        if (window.pywebview?.api?.get_system_status) {
          data = await window.pywebview.api.get_system_status();
        } else {
          const res = await fetch('/api/system-status');
          data = await res.json();
        }

        let summary = '';
        let reply = '';

        if (isSpecificBatteryQuery) {
          summary = `Battery: ${data.battery}`;
          reply = `Battery status: **${data.battery}**`;
        } else if (isSpecificCpuQuery) {
          summary = `CPU: ${data.cpu_percent}%`;
          reply = `CPU Utilization: **${data.cpu_percent}%** (${data.cpu_model || 'Processor'})`;
        } else if (isSpecificRamQuery) {
          summary = `RAM: ${data.ram_used_gb} GB / ${data.ram_total_gb} GB`;
          reply = `RAM Utilization: **${data.ram_used_gb} GB** used of **${data.ram_total_gb} GB** (${data.ram_percent}%)`;
        } else {
          summary = `OS: ${data.os_name}, CPU: ${data.cpu_percent}%, RAM: ${data.ram_used_gb}GB`;
          reply = `System telemetry report:\n\n- Battery: ${data.battery}\n- CPU Utilization: ${data.cpu_percent}%\n- RAM: ${data.ram_used_gb} GB used of ${data.ram_total_gb} GB (${data.ram_percent}%)\n- Disk Free Space: ${data.disk_free_gb} GB\n- System Uptime: ${data.uptime}\n- Operating System: ${data.os_name} (${data.os_version})\n- Python Runtime: ${data.python_version}`;
        }

        postToolAndReply('system_info', summary, reply, 28, 64);
      } catch (err: any) {
        postToolAndReply('system_info', 'failed', `Error reading telemetry: ${err.message}`);
      }
      setIsRunning(false);
      setStatusText('Ready');
      return;
    }

    // 2. Web Search Tool
    const isExplicitSearch =
      lower.startsWith('/search ') ||
      lower.startsWith('web search: ') ||
      lower.startsWith('google: ');
    if (isExplicitSearch) {
      const searchQuery = userText.replace(/^\/search\s+|^web search:\s+|^google:\s+/i, '').trim();
      const allowed = await checkPermission('web_search', 'Allows searching the web for coding references and live documentation.');
      if (!allowed) {
        postToolAndReply('web_search', 'Permission denied for web_search. Turn it on in Settings.', 'Permission denied for web_search. Turn it on in Settings.');
        setIsRunning(false);
        setStatusText('Ready');
        return;
      }

      try {
        let results: any[] = [];
        if (window.pywebview?.api?.web_search) {
          results = await window.pywebview.api.web_search(searchQuery || userText);
        } else {
          const res = await fetch('/api/web-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: searchQuery || userText }),
          });
          const data = await res.json();
          results = data.results || [];
        }
        const reply = `Latest technical references from web retrieval:\n\n${results
          .map((r: any, idx: number) => `**${idx + 1}. [${r.title}](${r.url})**\n${r.snippet}`)
          .join('\n\n')}`;
        postToolAndReply('web_search', `retrieved ${results.length} references`, reply, 45, 95);
      } catch (err: any) {
        postToolAndReply('web_search', 'failed', `Search failed: ${err.message}`);
      }
      setIsRunning(false);
      setStatusText('Ready');
      return;
    }

    // 3. Python Code Execution with AI Safety Guard & Human Review
    const isExplicitPythonRun =
      lower.startsWith('/run') ||
      lower.startsWith('/exec') ||
      lower.startsWith('run python:') ||
      (lower.includes('run python') && userText.includes('```'));
    if (isExplicitPythonRun) {
      const allowed = await checkPermission('python_exec', 'Warning: Allows executing arbitrary Python code in an isolated subprocess.');
      if (!allowed) {
        postToolAndReply('run_python', 'Permission denied for python_exec. Turn it on in Settings.', 'Permission denied for python_exec. Turn it on in Settings.');
        setIsRunning(false);
        setStatusText('Ready');
        return;
      }

      const codeMatch = userText.match(/```python\n([\s\S]*?)```/) || userText.match(/```([\s\S]*?)```/);
      const codeSnippet = codeMatch ? codeMatch[1] : userText.replace(/^\/run\s*|^\/exec\s*|^run python:\s*/i, '');

      setCurrentStepText('Running AI Code Safety Verification Thread');
      setNextStepText('Auditing AST and credential exposure');

      const isCriticalMalicious = /rm\s+-rf\s+[/~]/i.test(codeSnippet) || /open\s*\(.*\.env.*\)/i.test(codeSnippet);
      const isSensitive = /os\.remove/i.test(codeSnippet) || /shutil\.rmtree/i.test(codeSnippet);

      if (isCriticalMalicious) {
        const rejectMsg = `AI Safety Guard Rejected Execution: Prohibited destructive command or key exposure detected.`;
        postToolAndReply('run_python', 'safety check rejected dangerous code', rejectMsg);
        setIsRunning(false);
        setStatusText('Ready');
        return;
      }

      if (isSensitive && !autoApproveSafe) {
        const approvedByHuman = await requestHumanReview(codeSnippet, 'Code modifies or deletes filesystem entries.');
        if (!approvedByHuman) {
          postToolAndReply('run_python', 'human reviewer declined execution', 'Action cancelled by human safety reviewer.');
          setIsRunning(false);
          setStatusText('Ready');
          return;
        }
      }

      try {
        let data: any;
        if (window.pywebview?.api?.run_python) {
          data = await window.pywebview.api.run_python(codeSnippet);
        } else {
          const res = await fetch('/api/run-python', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: codeSnippet }),
          });
          data = await res.json();
        }
        const reply = `Executed Python in isolated process:\n\n\`\`\`python\n${codeSnippet.trim()}\n\`\`\`\n\nOutput:\n\`\`\`text\n${data.stdout || data.stderr || 'Execution finished (exit 0)'}\n\`\`\``;
        postToolAndReply('run_python', `exit code ${data.exit_code}`, reply, 40, 75);
      } catch (err: any) {
        postToolAndReply('run_python', 'execution error', `Error: ${err.message}`);
      }
      setIsRunning(false);
      setStatusText('Ready');
      return;
    }

    // 4. Standard Conversational API Turn with Attachments
    try {
      abortControllerRef.current = new AbortController();
      const primaryKey = apiKeySlots.find((s) => s.key.trim().length > 0)?.key || '';

      if (window.pywebview?.api?.chat) {
        const data = await window.pywebview.api.chat({
          message: userText,
          history: activeSession.messages.map((m) => ({
            role: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
          })),
          model: activeModel,
          thinkingLevel,
          customApiKey: primaryKey,
          mode: activeMode,
          attachments: currentAttachments,
        });

        if (data.error === 'API_KEY_MISSING') {
          await streamAssistantResponse(data.reply);
          setIsSettingsOpen(true);
        } else {
          // If the AI generated a plan with numbered/bulleted action steps, attach planData
          const planMatches = data.reply ? data.reply.match(/^\s*(?:\d+[\.\)]|\-|\*)\s+(.+)$/gm) : null;
          const isPlanLike =
            planMatches &&
            planMatches.length >= 3 &&
            (lower.includes('plan') || lower.includes('step') || lower.includes('build') || lower.includes('create') || lower.includes('workflow'));
          const extractedPlan = isPlanLike
            ? {
                title: userText.slice(0, 48),
                steps: planMatches.slice(0, 8).map((s: string) => s.replace(/^\s*(?:\d+[\.\)]|\-|\*)\s+/, '').trim()),
              }
            : undefined;

          await streamAssistantResponse(data.reply || 'Task completed.', extractedPlan);
          setTokenCounts({ input: data.inputTokens || 35, output: data.outputTokens || 80 });
        }
      } else {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userText,
            history: activeSession.messages.map((m) => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
            })),
            model: activeModel,
            thinkingLevel,
            customApiKey: primaryKey,
            mode: activeMode,
            attachments: currentAttachments,
          }),
          signal: abortControllerRef.current.signal,
        });

        const data = await res.json();
        if (!res.ok && data.error === 'API_KEY_MISSING') {
          await streamAssistantResponse(data.reply);
        } else {
          await streamAssistantResponse(data.reply || 'Task completed.');
          setTokenCounts({ input: data.inputTokens || 35, output: data.outputTokens || 80 });
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        await streamAssistantResponse(`Error: ${err.message}`);
      }
    } finally {
      setIsRunning(false);
      setStatusText('Ready');
      setCurrentStepText('');
      setNextStepText('');
    }
  };

  const postToolAndReply = (toolName: string, summary: string, reply: string, inTok = 25, outTok = 50) => {
    const toolMsg: Message = {
      id: `t-${Date.now()}`,
      role: 'tool',
      content: `Used: ${toolName}, ${summary}`,
      timestamp: new Date().toLocaleTimeString(),
    };
    const assistantMsg: Message = {
      id: `a-${Date.now() + 1}`,
      role: 'assistant',
      content: reply,
      tokens: { input: inTok, output: outTok },
      timestamp: new Date().toLocaleTimeString(),
    };

    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, messages: [...s.messages, toolMsg, assistantMsg] } : s))
    );
    setStatusText(`Used: ${toolName}, ${summary}`);
    setTokenCounts({ input: inTok, output: outTok });
  };

  const handleStop = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsRunning(false);
    setStatusText('Task cancelled by user.');
    setCurrentStepText('');
    setNextStepText('');
    setSessions((prev) =>
      prev.map((s) => ({
        ...s,
        messages: s.messages.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
      }))
    );
  };

  const createNewChat = () => {
    const newId = `sess-${Date.now()}`;
    const newSession: ChatSession = {
      id: newId,
      title: 'New Conversation',
      messages: [
        {
          id: `msg-${Date.now()}`,
          role: 'system',
          content: 'Zeno is ready. Type a message or attach files/images to start.',
          timestamp: new Date().toLocaleTimeString(),
        },
      ],
      created_at: Date.now(),
      last_activity: Date.now(),
      flagged_for_deletion: false,
      agentState: {
        hasTask: false,
        status: 'standby',
        plan: null,
        scratchpad: [],
        thoughts: [],
        workspaceFiles: [],
      },
    };
    setSessions((prev) => {
      const updated = [newSession, ...prev];
      if (window.pywebview?.api?.save_chats) {
        window.pywebview.api.save_chats(updated);
      }
      return updated;
    });
    setActiveSessionId(newId);
    setIsSettingsOpen(false);
  };

  const saveSettings = async () => {
    try {
      localStorage.setItem('zeno_api_key_slots', JSON.stringify(apiKeySlots));
      localStorage.setItem('zeno_active_model', activeModel);
    } catch {}

    if (window.pywebview?.api?.save_settings) {
      try {
        const result = await window.pywebview.api.save_settings({
          apiKeySlots,
          activeModel,
          thinkingLevel,
          autoSwitch,
          defaultWorkspace,
          autoApproveSafe,
          webSearchEnabled,
          permissions,
        });
        if (result === true) {
          setSettingsSavedNotice('✓ Settings & API keys saved successfully');
        } else {
          setSettingsSavedNotice('⚠ Save may have failed — check the .env file');
        }
      } catch (err: any) {
        setSettingsSavedNotice(`✗ Save error: ${err.message}`);
      }
    } else {
      // Running in browser (no pywebview) — just show a notice
      setSettingsSavedNotice('Settings saved (browser mode — no .env persistence)');
    }
    setTimeout(() => setSettingsSavedNotice(''), 4000);
  };

  // Toggle compacted memory inspection
  const toggleMemoryExpanded = (id: string) => {
    setExpandedMemoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Intelligent Context Compaction to optimize token consumption without losing intelligence
  const handleCompactChat = async () => {
    const active = sessions.find((s) => s.id === activeSessionId);
    if (!active || isCompacting || isRunning) return;

    // Filter out previous compacted banners or empty placeholders
    const regularMessages = active.messages.filter((m) => !m.isCompactedMemory && m.role !== 'system');
    if (regularMessages.length < 4) {
      setCompactToast('Chat is already compact (less than 4 turns).');
      setTimeout(() => setCompactToast(''), 3000);
      return;
    }

    // Keep the most recent 4 messages verbatim to preserve active conversation flow and context!
    const splitIndex = Math.max(0, active.messages.length - 4);
    const olderMessages = active.messages.slice(0, splitIndex);
    const recentMessages = active.messages.slice(splitIndex);

    if (olderMessages.length === 0) return;

    setIsCompacting(true);
    setStatusText('Compacting conversation memory...');
    const primaryKey = apiKeySlots.find((s) => s.key.trim().length > 0)?.key || '';

    try {
      let data: any;
      if (window.pywebview?.api?.compact_conversation) {
        data = await window.pywebview.api.compact_conversation({
          messages: olderMessages.map((m) => ({ role: m.role, content: m.content })),
          model: activeModel,
          customApiKey: primaryKey,
        });
      } else {
        // Fallback local distillation
        const topics = olderMessages
          .filter((m) => m.role === 'user')
          .map((m) => m.content.slice(0, 60))
          .slice(0, 4);
        data = {
          summary: `### 🧠 Compacted Conversation Memory\n- **Primary Objective**: ${topics.join('; ') || 'Technical dialogue'}\n- **Context**: ${olderMessages.length} historical turns condensed to save tokens while preserving core decisions.`,
          savedTokens: Math.round(olderMessages.length * 120),
          compactedCount: olderMessages.length,
        };
      }

      if (data.summary) {
        const compactedMessage: Message = {
          id: `compacted-${Date.now()}`,
          role: 'system',
          content: data.summary,
          timestamp: new Date().toLocaleTimeString(),
          isCompactedMemory: true,
          archivedCount: olderMessages.length,
          savedTokens: data.savedTokens || Math.round(olderMessages.length * 140),
          archivedMessages: olderMessages,
        };

        const updatedSessions = sessions.map((s) => {
          if (s.id === activeSessionId) {
            return {
              ...s,
              messages: [compactedMessage, ...recentMessages],
              last_activity: Date.now(),
            };
          }
          return s;
        });

        setSessions(updatedSessions);
        if (window.pywebview?.api?.save_chats) {
          window.pywebview.api.save_chats(updatedSessions);
        }

        setCompactToast(`Context compacted! Saved ~${data.savedTokens || 800} tokens with zero intelligence loss.`);
        setTimeout(() => setCompactToast(''), 4500);
      }
    } catch (err: any) {
      setCompactToast(`Compaction failed: ${err.message}`);
      setTimeout(() => setCompactToast(''), 3000);
    } finally {
      setIsCompacting(false);
      setStatusText('Ready');
    }
  };

  // Render markdown with code block copy buttons and rich typography once done
  const renderMessageContent = (content: string, isStreaming?: boolean) => {
    // While actively streaming, show live streaming text with blinking cursor
    if (isStreaming) {
      return (
        <div className="whitespace-pre-wrap leading-relaxed text-[#E6E8EE]">
          {content}
          <span className="inline-block w-1.5 h-3.5 bg-[#3B82F6] animate-pulse ml-1 align-middle rounded-sm" />
        </div>
      );
    }

    // Once the agent is done, normalize any unclosed code block so it parses cleanly
    let normalizedContent = content;
    const tripleBackticks = (content.match(/```/g) || []).length;
    if (tripleBackticks % 2 !== 0) {
      normalizedContent += '\n```';
    }

    const parts: { type: 'text' | 'code'; text?: string; code?: string; lang?: string }[] = [];
    const codeBlockRegex = /```([a-zA-Z0-9_\-\.\+]*)\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(normalizedContent)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: 'text', text: normalizedContent.slice(lastIndex, match.index) });
      }
      parts.push({ type: 'code', lang: match[1] || 'code', code: match[2] });
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < normalizedContent.length) {
      parts.push({ type: 'text', text: normalizedContent.slice(lastIndex) });
    }

    return (
      <div className="space-y-3">
        {parts.map((p, idx) => {
          if (p.type === 'text') {
            const rawText = p.text || '';
            if (!rawText.trim()) return null;

            let html = '';
            try {
              html = marked.parse(rawText, {
                gfm: true,
                breaks: true,
                async: false,
              }) as string;
            } catch {
              html = rawText;
            }

            return (
              <div
                key={idx}
                className="markdown-content text-xs text-[#E6E8EE]"
                dangerouslySetInnerHTML={{ __html: html }}
              />
            );
          } else {
            const codeContent = p.code || '';
            const codeLang = p.lang || 'code';
            const blockId = `code-${idx}-${codeContent.length}`;
            const isCopied = copiedCodeId === blockId;
            return (
              <div key={idx} className="my-3 overflow-hidden rounded border border-[#22222A] bg-[#0F0F13]">
                <div className="flex items-center justify-between border-b border-[#22222A] bg-[#14141A] px-3 py-1.5 text-xs text-[#7C8091]">
                  <span className="font-mono font-medium">{codeLang.toLowerCase()}</span>
                  <button
                    onClick={() => handleCopy(codeContent, blockId)}
                    className="flex items-center gap-1.5 rounded px-2 py-0.5 text-xs text-[#E6E8EE] hover:bg-[#22222E] cursor-pointer transition-colors"
                  >
                    {isCopied ? (
                      <>
                        <Check className="h-3 w-3 text-[#4ADE80]" />
                        <span className="text-[#4ADE80]">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 text-[#7C8091]" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="overflow-x-auto p-3 font-mono text-xs text-[#CBD5E1] leading-relaxed">
                  <code>{codeContent}</code>
                </pre>
              </div>
            );
          }
        })}
      </div>
    );
  };

  return (
    <div className="flex h-screen w-screen flex-col bg-[#0A0A0C] text-[#E6E8EE] select-text font-sans">
      {/* Hidden File Inputs for Plus (+) Attachment Menu */}
      <input
        ref={docFileInputRef}
        type="file"
        multiple
        onChange={handleFileSelect}
        className="hidden"
        accept=".txt,.py,.json,.csv,.md,.docx,.pdf,.log,.ts,.tsx,.js,.jsx,.html,.css,.sql,.java,.c,.cpp"
      />
      <input
        ref={imageFileInputRef}
        type="file"
        multiple
        onChange={handleFileSelect}
        className="hidden"
        accept="image/*"
      />

      {/* Top Application Bar */}
      <header className="flex h-11 items-center justify-between border-b border-[#22222A] bg-[#111115] px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 mr-1">
            <span className="h-3 w-3 rounded-full bg-[#F87171]/80 inline-block" />
            <span className="h-3 w-3 rounded-full bg-[#EAB308]/80 inline-block" />
            <span className="h-3 w-3 rounded-full bg-[#4ADE80]/80 inline-block" />
          </div>
          <ZenoLogo size={22} glow />
          <span className="text-sm font-bold tracking-tight text-[#E6E8EE]">Zeno</span>
          <span className="rounded bg-[#22222A] px-2 py-0.5 text-[11px] text-[#7C8091] hidden md:inline-block">Desktop Assistant</span>
        </div>

        {/* Dual Mode Switcher: Chat Assistant vs Agentic Worker */}
        <div className="flex items-center rounded border border-[#22222A] bg-[#0A0A0C] p-0.5 text-xs">
          <button
            onClick={() => setActiveMode('chat')}
            className={`flex items-center gap-1.5 rounded px-3 py-1 transition-colors ${
              activeMode === 'chat'
                ? 'bg-[#3B82F6] font-medium text-white'
                : 'text-[#7C8091] hover:text-[#E6E8EE]'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Chat Assistant
          </button>
          <button
            onClick={() => setActiveMode('agentic')}
            className={`flex items-center gap-1.5 rounded px-3 py-1 transition-colors ${
              activeMode === 'agentic'
                ? 'bg-[#3B82F6] font-medium text-white'
                : 'text-[#7C8091] hover:text-[#E6E8EE]'
            }`}
          >
            <Bot className="h-3.5 w-3.5" />
            Agentic Worker
          </button>
        </div>

        {/* In-Chat Model & Thinking Level Controls strictly based on Provided Keys */}
        <div className="flex items-center gap-2 text-xs">
          {/* Compact Chat Button */}
          {activeSession.messages.filter((m) => !m.isCompactedMemory && m.role !== 'system').length >= 4 && (
            <button
              onClick={handleCompactChat}
              disabled={isCompacting || isRunning}
              title="Intelligently compress older turns into high-density memory to save tokens while keeping AI smart"
              className="flex items-center gap-1.5 rounded border border-[#3B82F6]/40 bg-[#1E3A8A]/30 px-2.5 py-1 text-xs text-[#93C5FD] hover:bg-[#1E3A8A]/50 hover:border-[#3B82F6] disabled:opacity-40 transition-all cursor-pointer"
            >
              <Sparkles className={`h-3 w-3 text-[#38BDF8] ${isCompacting ? 'animate-spin' : ''}`} />
              <span>{isCompacting ? 'Compacting...' : 'Compact History'}</span>
            </button>
          )}

          {availableModels.length > 0 ? (
            <select
              value={activeModel}
              onChange={(e) => setActiveModel(e.target.value)}
              className="rounded border border-[#22222A] bg-[#17171D] px-2.5 py-1 text-xs text-[#E6E8EE] outline-none cursor-pointer"
            >
              {availableModels.map((m) => (
                <option key={m} value={m}>
                  {MODEL_DISPLAY_LABELS[m] || m}
                </option>
              ))}
            </select>
          ) : (
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="rounded border border-[#F87171]/40 bg-[#F87171]/10 px-2.5 py-1 text-xs text-[#F87171] hover:bg-[#F87171]/20"
            >
              No API Key (Open Settings)
            </button>
          )}

          <div className="flex items-center rounded border border-[#22222A] bg-[#17171D] px-2 py-1 text-xs text-[#7C8091]">
            <span className="mr-1.5">Thinking:</span>
            <select
              value={thinkingLevel}
              onChange={(e) => setThinkingLevel(e.target.value)}
              className="bg-transparent text-xs text-[#3B82F6] font-medium outline-none cursor-pointer"
            >
              {THINKING_LEVELS.map((lvl) => (
                <option key={lvl} value={lvl} className="bg-[#17171D] text-[#E6E8EE]">
                  {lvl}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Main Workspace Frame */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar (240px) */}
        {sidebarVisible && (
          <aside className="flex w-[240px] flex-col border-r border-[#22222A] bg-[#111115]">
            {/* Sidebar Brand Header */}
            <div className="flex items-center gap-2.5 px-3 pt-3 pb-2 border-b border-[#22222A]/60">
              <ZenoLogo size={22} glow />
              <div>
                <div className="text-xs font-bold text-[#E6E8EE] tracking-wide">ZENO STUDIO</div>
                <div className="text-[10px] text-[#38BDF8] flex items-center gap-1 font-mono">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#4ADE80] animate-pulse" />
                  Neural Assistant
                </div>
              </div>
            </div>

            <div className="p-3">
              <button
                onClick={createNewChat}
                className="w-full rounded bg-[#3B82F6] py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#2563EB]"
              >
                New chat
              </button>
            </div>

            <div className="px-3 pb-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search chats..."
                className="w-full rounded border border-[#22222A] bg-[#17171D] px-2.5 py-1 text-xs text-[#E6E8EE] placeholder-[#7C8091] outline-none focus:border-[#3B82F6]"
              />
            </div>

            {/* Chat Sessions list with 3-day deletion flag */}
            <div className="flex-1 overflow-y-auto px-2 space-y-1">
              {sessions
                .filter((s) => s.title.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((s) => {
                  const isActive = s.id === activeSessionId;
                  return (
                    <div
                      key={s.id}
                      onClick={() => {
                        setActiveSessionId(s.id);
                        setIsSettingsOpen(false);
                      }}
                      className={`group flex cursor-pointer flex-col rounded p-2 text-xs transition-colors ${
                        isActive
                          ? 'bg-[#181820] text-[#E6E8EE] border-l-2 border-[#3B82F6]'
                          : 'text-[#7C8091] hover:bg-[#1D1D27] hover:text-[#E6E8EE]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="truncate font-medium flex-1">{s.title}</div>
                        <button
                          onClick={(e) => handleDeleteChat(s.id, e)}
                          title="Delete conversation"
                          className="ml-1 rounded p-1 text-[#7C8091] opacity-0 group-hover:opacity-100 hover:bg-[#2A2A38] hover:text-[#F87171] transition-all"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                      {s.flagged_for_deletion && (
                        <div className="mt-1 flex items-center justify-between text-[10px] text-[#F87171]">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            Flagged for deletion in {s.hours_until_purge || 24}h
                          </span>
                          <button
                            onClick={(e) => handleUnflagChat(s.id, e)}
                            className="rounded bg-[#22222E] px-1.5 py-0.5 text-[9px] text-[#4ADE80] hover:bg-[#2A2A38]"
                          >
                            Keep
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>

            {/* Sidebar Footer with Settings */}
            <div className="border-t border-[#22222A] p-2">
              <button
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className="flex w-full items-center gap-2 rounded px-3 py-2 text-xs text-[#7C8091] hover:bg-[#1E1E26] hover:text-[#E6E8EE]"
              >
                <Settings className="h-3.5 w-3.5" />
                Settings
              </button>
            </div>
          </aside>
        )}

        {/* Central Content View */}
        <main className="flex flex-1 flex-col overflow-hidden bg-[#0A0A0C]">
          {/* Top Bar (48px) */}
          <div className="flex h-12 items-center justify-between border-b border-[#22222A] bg-[#0D0D11] px-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarVisible(!sidebarVisible)}
                className="rounded px-2 py-1 text-xs text-[#7C8091] hover:bg-[#181822] hover:text-[#E6E8EE]"
              >
                {sidebarVisible ? 'Hide' : 'Show'}
              </button>
              <span className="text-xs text-[#7C8091]">
                {isSettingsOpen ? 'Settings' : activeSession.title}
              </span>
            </div>

            {/* Live Progress Indicator */}
            {isRunning && currentStepText && (
              <div className="flex items-center gap-2 rounded bg-[#17171D] px-3 py-1 text-xs text-[#3B82F6]">
                <Activity className="h-3.5 w-3.5 animate-spin" />
                <span className="truncate max-w-sm">{currentStepText}</span>
              </div>
            )}

            <div className="flex items-center gap-3 text-xs text-[#7C8091]">
              <span className="rounded bg-[#17171D] px-2 py-0.5 text-[11px] font-mono text-[#E6E8EE]">
                {activeMode === 'chat' ? 'Chat Assistant Mode' : 'Agentic Worker Mode'}
              </span>
            </div>
          </div>

          {/* Body: Either Settings View or Interactive Stream */}
          {isSettingsOpen ? (
            /* FULL-PANEL SETTINGS VIEW */
            <div className="w-full flex-1 overflow-y-auto p-6 md:p-8 bg-[#0A0A0C]">
              <div className="w-full max-w-5xl mx-auto space-y-6">
                <div className="mb-6 flex items-center justify-between border-b border-[#22222A] pb-4">
                  <button
                    onClick={() => setIsSettingsOpen(false)}
                    className="flex items-center gap-1.5 rounded bg-[#17171D] border border-[#22222A] px-3.5 py-1.5 text-xs font-semibold text-[#93C5FD] hover:bg-[#1E293B] hover:text-white transition-colors cursor-pointer"
                  >
                    ← Back to Assistant
                  </button>
                  <div className="flex items-center gap-2.5">
                    <ZenoLogo size={22} glow />
                    <h2 className="text-base font-bold text-[#E6E8EE]">Settings &amp; AI Configuration</h2>
                  </div>
                  <div className="w-24" />
                </div>

                <div className="space-y-6">
                  {/* 1. Dynamic 3-Field API Key Checklist */}
                  <div className="rounded-md border border-[#22222A] bg-[#17171D] p-5">
                    <h3 className="mb-1 text-sm font-bold text-[#E6E8EE]">API Key Configuration (3 Flexible Slots)</h3>
                    <p className="mb-4 text-xs text-[#7C8091]">
                      Zeno strictly requires a personal API key. Select any provider for each slot and enter your key underneath.
                    </p>

                    <div className="space-y-4">
                      {apiKeySlots.map((slot, idx) => (
                        <div key={slot.id} className="rounded border border-[#22222A] bg-[#131318] p-3.5">
                          <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs font-semibold text-[#E6E8EE]">Key Slot {idx + 1}</span>
                            <select
                              value={slot.provider}
                              onChange={(e) => {
                                const updated = [...apiKeySlots];
                                updated[idx].provider = e.target.value;
                                setApiKeySlots(updated);
                              }}
                              className="rounded border border-[#22222A] bg-[#17171D] px-2 py-1 text-xs text-[#3B82F6] font-medium outline-none"
                            >
                              {PROVIDERS.map((prov) => (
                                <option key={prov} value={prov}>
                                  {prov}
                                </option>
                              ))}
                            </select>
                          </div>
                          <input
                            type="password"
                            value={slot.key}
                            onChange={(e) => {
                              const updated = [...apiKeySlots];
                              updated[idx].key = e.target.value;
                              setApiKeySlots(updated);
                            }}
                            placeholder={`Enter ${slot.provider} API Key...`}
                            className="w-full rounded border border-[#22222A] bg-[#0F0F13] px-3 py-1.5 text-xs text-[#E6E8EE] outline-none focus:border-[#3B82F6]"
                          />
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <button
                        onClick={saveSettings}
                        className="rounded bg-[#3B82F6] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#2563EB]"
                      >
                        Save Settings
                      </button>
                      <button
                        onClick={() => {
                          const updated = [...apiKeySlots];
                          updated[0] = { id: 'slot-1', provider: 'Gemini', key: 'AIzaSyDemoKey_' + Math.random().toString(36).substring(7) };
                          setApiKeySlots(updated);
                          setSettingsSavedNotice('Gemini Demo key set in Slot 1. Models activated!');
                          setTimeout(() => setSettingsSavedNotice(''), 3000);
                        }}
                        className="rounded border border-[#3B82F6]/50 bg-[#172554] px-3 py-1.5 text-xs text-[#93C5FD] hover:bg-[#1E3A8A]"
                      >
                        Use Demo Key for Testing
                      </button>
                      <button
                        onClick={() => {
                          setApiKeySlots([
                            { id: 'slot-1', provider: 'Gemini', key: '' },
                            { id: 'slot-2', provider: 'Anthropic Claude', key: '' },
                            { id: 'slot-3', provider: 'OpenRouter', key: '' },
                          ]);
                          setSettingsSavedNotice('All API keys cleared');
                          setTimeout(() => setSettingsSavedNotice(''), 3000);
                        }}
                        className="rounded border border-[#22222A] bg-[#17171D] px-3 py-1.5 text-xs text-[#7C8091] hover:bg-[#22222E] hover:text-[#E6E8EE]"
                      >
                        Clear All Keys
                      </button>
                      {settingsSavedNotice && <span className="text-xs text-[#4ADE80]">{settingsSavedNotice}</span>}
                    </div>
                  </div>

                  {/* 2. Workspace & AI Safety Guard */}
                  <div className="rounded-md border border-[#22222A] bg-[#17171D] p-5">
                    <h3 className="mb-1 text-sm font-bold text-[#E6E8EE]">AI Workspace Directory</h3>
                    <p className="mb-3 text-xs text-[#7C8091]">
                      Default directory where all multi-step projects and organized documents are created.
                    </p>
                    <input
                      type="text"
                      value={defaultWorkspace}
                      onChange={(e) => setDefaultWorkspace(e.target.value)}
                      className="w-full rounded border border-[#22222A] bg-[#0F0F13] px-3 py-1.5 text-xs text-[#E6E8EE] outline-none focus:border-[#3B82F6] mb-4"
                    />

                    <div className="border-t border-[#22222A] pt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs font-semibold text-[#E6E8EE]">AI Safety Guard: Auto-Approve Safe Code</div>
                          <div className="text-[11px] text-[#7C8091]">
                            Runs a secondary verification thread to audit AST patterns. Modifying root system folders triggers human review.
                          </div>
                        </div>
                        <input
                          type="checkbox"
                          checked={autoApproveSafe}
                          onChange={(e) => setAutoApproveSafe(e.target.checked)}
                          className="h-4 w-4 rounded border-[#22222A] accent-[#3B82F6]"
                        />
                      </div>

                      <div className="flex items-center justify-between pt-2">
                        <div>
                          <div className="text-xs font-semibold text-[#E6E8EE]">Web Search Tool for Live Documentation</div>
                          <div className="text-[11px] text-[#7C8091]">
                            Enables the agent to retrieve latest code specs and web documentation.
                          </div>
                        </div>
                        <input
                          type="checkbox"
                          checked={webSearchEnabled}
                          onChange={(e) => setWebSearchEnabled(e.target.checked)}
                          className="h-4 w-4 rounded border-[#22222A] accent-[#3B82F6]"
                        />
                      </div>
                    </div>
                  </div>

                  {/* 3. Tool Permissions */}
                  <div className="rounded-md border border-[#22222A] bg-[#17171D] p-5">
                    <h3 className="mb-3 text-sm font-bold text-[#E6E8EE]">Tool Permissions</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      {CATEGORIES.map((cat) => (
                        <div key={cat.id} className="flex items-center justify-between p-3 rounded border border-[#22222A] bg-[#131318] hover:border-[#3B82F6]/40 transition-colors">
                          <div className="pr-3">
                            <div className="text-xs font-semibold text-[#E6E8EE]">{cat.name}</div>
                            <div className="text-[11px] text-[#7C8091]">{cat.desc}</div>
                          </div>
                          <input
                            type="checkbox"
                            checked={permissions[cat.id] || false}
                            onChange={(e) => setPermissions((prev) => ({ ...prev, [cat.id]: e.target.checked }))}
                            className="h-4 w-4 rounded border-[#22222A] accent-[#3B82F6]"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 4. User Memory & Personalization (Claude / ChatGPT Logic) */}
                  <div className="rounded-md border border-[#22222A] bg-[#17171D] p-5">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <BrainCircuit className="h-4 w-4 text-[#38BDF8]" />
                        <h3 className="text-sm font-bold text-[#E6E8EE]">User Memory &amp; Personalization</h3>
                      </div>
                      <span className="rounded bg-[#1E293B] px-2 py-0.5 text-[10px] text-[#93C5FD] font-mono border border-[#3B82F6]/30">
                        MEMORY.md
                      </span>
                    </div>
                    <p className="mb-4 text-xs text-[#7C8091] leading-relaxed">
                      Zeno remembers details about you, your preferences, coding habits, and project contexts across all conversations.
                    </p>

                    {/* Active Memory Markdown Display & Direct Editor */}
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-1.5 text-xs">
                        <span className="font-semibold text-[#CBD5E1]">Active Memory File</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={handleClearMemory}
                            className="text-[11px] text-[#F87171] hover:underline cursor-pointer"
                          >
                            Reset to Default
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={memoryText}
                        onChange={(e) => setMemoryText(e.target.value)}
                        rows={6}
                        placeholder="Loading persistent memory..."
                        className="w-full rounded border border-[#22222A] bg-[#0F0F13] p-3 font-mono text-xs text-[#CBD5E1] outline-none focus:border-[#3B82F6] leading-relaxed resize-y"
                      />
                      <div className="mt-2 flex justify-end">
                        <button
                          onClick={handleSaveMemoryDirect}
                          disabled={isSavingMemory}
                          className="rounded bg-[#22222E] border border-[#3B82F6]/40 px-3 py-1 text-xs font-semibold text-[#93C5FD] hover:bg-[#2A2A38] cursor-pointer"
                        >
                          {isSavingMemory ? 'Saving...' : 'Save Memory Direct'}
                        </button>
                      </div>
                    </div>

                    {/* Import Memories with AI Synthesizer */}
                    <div className="border-t border-[#22222A] pt-4">
                      <h4 className="text-xs font-semibold text-[#E6E8EE] mb-1">Import Memories (AI Synthesis)</h4>
                      <p className="text-[11px] text-[#7C8091] mb-2">
                        Paste notes, background info, or memories exported from Claude or ChatGPT. Zeno's AI will synthesize and intelligently merge them into your memory file.
                      </p>
                      <textarea
                        value={importNotes}
                        onChange={(e) => setImportNotes(e.target.value)}
                        rows={3}
                        placeholder="Paste memories or notes here (e.g., 'My name is Alex, I build React and Python apps, I prefer concise code with type hints...')"
                        className="w-full rounded border border-[#22222A] bg-[#0F0F13] p-2.5 text-xs text-[#E6E8EE] placeholder-[#7C8091] outline-none focus:border-[#3B82F6] mb-2.5 resize-none"
                      />
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-[#4ADE80]">{memoryNotice}</span>
                        <button
                          onClick={handleImportMemoryAI}
                          disabled={isImportingMemory || !importNotes.trim()}
                          className="flex items-center gap-1.5 rounded bg-[#3B82F6] px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-40 hover:bg-[#2563EB] cursor-pointer"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          {isImportingMemory ? 'Synthesizing with AI...' : 'Save & Synthesize with AI'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : activeMode === 'agentic' ? (
            /* AGENTIC WORKER VIEW: STANDBY DEFAULT VS ACTIVE 3-COLUMN WORKSPACE */
            !activeAgentState.hasTask ? (
              /* STANDBY / WAITING UI (DEFAULT STATE WHEN IDLE) */
              <div className="flex flex-1 flex-col items-center justify-between p-6 bg-[#0A0A0C] overflow-y-auto">
                <div className="max-w-2xl w-full text-center space-y-6 pt-6">
                  {/* Standby Status Badge */}
                  <div className="inline-flex items-center gap-2 rounded-full border border-[#22222A] bg-[#111115] px-3.5 py-1.5 text-xs text-[#7C8091]">
                    <span className="h-2 w-2 rounded-full bg-[#3B82F6] animate-pulse" />
                    <span className="font-medium text-[#CBD5E1]">Agent Worker: Standby</span>
                  </div>

                  <div>
                    <h2 className="text-xl font-bold tracking-tight text-[#E6E8EE] mb-2">
                      Autonomous Agent Standby
                    </h2>
                    <p className="text-xs text-[#7C8091] leading-relaxed max-w-lg mx-auto">
                      Each chat functions as an independent agent worker workspace with its own memory, execution plan, thoughts, and generated files. This session has no task currently running.
                    </p>
                  </div>

                  {/* 3 Quick Starter Action Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-left pt-2">
                    <button
                      onClick={() =>
                        launchAgenticTask('Workspace Architecture Setup', [
                          `Scan repository layout and filesystem permissions in ${defaultWorkspace}`,
                          'Audit existing directories for documentation, source trees, and configurations',
                          'Generate organized workspace directory structure and manifest files',
                          'Establish baseline environment configurations and path aliases',
                          'Implement repository linting and static analysis configuration',
                          'Author healthcheck diagnostic script for workspace validation',
                          'Execute healthcheck script and verify execution results',
                          'Compile workspace architecture report into reports/workspace_audit.md',
                        ])
                      }
                      className="rounded border border-[#22222A] bg-[#111115] p-3.5 text-xs hover:border-[#3B82F6] hover:bg-[#15151D] transition-all flex flex-col justify-between group cursor-pointer"
                    >
                      <div>
                        <div className="font-semibold text-[#E6E8EE] flex items-center gap-1.5 mb-1.5">
                          <FolderOpen className="h-4 w-4 text-[#3B82F6]" />
                          Workspace Architecture
                        </div>
                        <div className="text-[11px] text-[#7C8091] leading-normal">
                          Deep-dive 8-phase filesystem analysis, structure manifest, and validation audit.
                        </div>
                      </div>
                      <div className="mt-4 flex items-center gap-1 text-[11px] text-[#3B82F6] font-medium group-hover:translate-x-0.5 transition-transform">
                        <span>Launch 8-Phase Task</span>
                        <ArrowRight className="h-3 w-3" />
                      </div>
                    </button>

                    <button
                      onClick={() =>
                        launchAgenticTask('Python Benchmark & AST Verification', [
                          'Initialize isolated execution sandbox with telemetry hooks',
                          'Inspect target Python environment, runtime version, and installed packages',
                          'Generate benchmark workload script with timing and memory metrics',
                          'Perform AST safety analysis to ensure zero destructive syscalls',
                          'Execute benchmark simulation using run_python with strict timeout bounds',
                          'Record memory profiles, CPU execution intervals, and latency percentiles',
                          'Author automated verification assertions against benchmark outputs',
                          'Compile comprehensive benchmark report into benchmark_results.json',
                        ])
                      }
                      className="rounded border border-[#22222A] bg-[#111115] p-3.5 text-xs hover:border-[#3B82F6] hover:bg-[#15151D] transition-all flex flex-col justify-between group cursor-pointer"
                    >
                      <div>
                        <div className="font-semibold text-[#E6E8EE] flex items-center gap-1.5 mb-1.5">
                          <FileCode className="h-4 w-4 text-[#3B82F6]" />
                          Python Benchmark
                        </div>
                        <div className="text-[11px] text-[#7C8091] leading-normal">
                          8-phase runtime profile, AST security audit, and JSON benchmark synthesis.
                        </div>
                      </div>
                      <div className="mt-4 flex items-center gap-1 text-[11px] text-[#3B82F6] font-medium group-hover:translate-x-0.5 transition-transform">
                        <span>Launch 8-Phase Task</span>
                        <ArrowRight className="h-3 w-3" />
                      </div>
                    </button>

                    <button
                      onClick={() =>
                        launchAgenticTask('Technical Specification & Synthesis', [
                          'Analyze source code architecture and module dependencies',
                          'Extract API interfaces, function signatures, and docstrings',
                          'Synthesize architectural blueprints and system flow diagrams',
                          'Document security boundary controls and permission schemas',
                          'Draft installation, configuration, and troubleshooting guides',
                          'Compile API reference documentation with practical usage examples',
                          'Validate markdown formatting and document link integrity',
                          'Publish finalized technical specification into docs/SPECIFICATION.md',
                        ])
                      }
                      className="rounded border border-[#22222A] bg-[#111115] p-3.5 text-xs hover:border-[#3B82F6] hover:bg-[#15151D] transition-all flex flex-col justify-between group cursor-pointer"
                    >
                      <div>
                        <div className="font-semibold text-[#E6E8EE] flex items-center gap-1.5 mb-1.5">
                          <FileText className="h-4 w-4 text-[#3B82F6]" />
                          Technical Synthesis
                        </div>
                        <div className="text-[11px] text-[#7C8091] leading-normal">
                          8-phase architectural documentation, interface spec, and markdown synthesis.
                        </div>
                      </div>
                      <div className="mt-4 flex items-center gap-1 text-[11px] text-[#3B82F6] font-medium group-hover:translate-x-0.5 transition-transform">
                        <span>Launch 8-Phase Task</span>
                        <ArrowRight className="h-3 w-3" />
                      </div>
                    </button>
                  </div>

                  {/* Context Info Box */}
                  <div className="rounded border border-[#22222A] bg-[#0E0E12] p-3.5 text-left flex items-center justify-between text-xs">
                    <div>
                      <div className="text-[10px] text-[#7C8091] uppercase font-semibold">Active Session Workspace</div>
                      <div className="font-mono text-xs text-[#CBD5E1] truncate">{defaultWorkspace}</div>
                    </div>
                    <button
                      onClick={() => setActiveMode('chat')}
                      className="rounded bg-[#17171D] border border-[#22222A] px-3 py-1 text-xs text-[#3B82F6] hover:bg-[#20202A] cursor-pointer"
                    >
                      Return to Chat
                    </button>
                  </div>
                </div>

                {/* Standby Instruction Input Bar */}
                <div className="w-full max-w-2xl mt-6">
                  <div className="flex rounded border border-[#22222A] bg-[#17171D] p-2 focus-within:border-[#3B82F6]">
                    <textarea
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          if (inputText.trim()) {
                            const text = inputText;
                            launchAgenticTask(`Agent Task: ${text.slice(0, 32)}`, text);
                          }
                        }
                      }}
                      placeholder="Instruct this independent agent worker to start a task..."
                      rows={1}
                      className="flex-1 resize-none bg-transparent px-2 py-1 text-xs text-[#E6E8EE] placeholder-[#7C8091] outline-none"
                    />
                    <button
                      onClick={() => {
                        if (inputText.trim()) {
                          const text = inputText;
                          launchAgenticTask(`Agent Task: ${text.slice(0, 32)}`, text);
                        }
                      }}
                      disabled={!inputText.trim()}
                      className="rounded bg-[#3B82F6] px-3.5 py-1 text-xs font-semibold text-white disabled:opacity-40 hover:bg-[#2563EB] cursor-pointer"
                    >
                      Launch Agent Task
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* ACTIVE AGENT MISSION CONTROL WORKSPACE */
              (() => {
                const planSteps = activeAgentState.plan?.steps || [];
                const completedStepsCount = planSteps.filter((s) => s.completed).length;
                const totalStepsCount = planSteps.length;
                const currentStepIdx = activeAgentState.plan?.currentStepIdx ?? 0;
                const progressPercent =
                  totalStepsCount > 0 ? Math.round((completedStepsCount / totalStepsCount) * 100) : 0;
                const currentActiveStep =
                  planSteps[currentStepIdx]?.text || (isRunning ? currentStepText : 'Awaiting directive...');

                return (
                  <div className="flex flex-1 flex-col overflow-hidden bg-[#0A0A0E]">
                    {/* MISSION CONTROL TOP HUD */}
                    <div className="border-b border-[#1E1E28] bg-[#0E0E14] px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-md z-10 shrink-0">
                      {/* Left: Dual-Agent Telemetry Badges */}
                      <div className="flex items-center gap-2.5">
                        {/* Zeno Builder Core */}
                        <div className="flex items-center gap-2 rounded-lg border border-[#3B82F6]/30 bg-[#141A29]/80 px-3 py-1.5 backdrop-blur-xs">
                          <div className="relative flex items-center justify-center">
                            <Cpu className="h-4 w-4 text-[#60A5FA]" />
                            {isRunning && (
                              <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-[#3B82F6] animate-ping" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[11px] font-bold text-[#E6E8EE]">Zeno Builder</span>
                              <span
                                className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-semibold ${
                                  isRunning
                                    ? 'bg-[#3B82F6]/20 text-[#93C5FD] border border-[#3B82F6]/40'
                                    : 'bg-[#1E1E28] text-[#7C8091]'
                                }`}
                              >
                                {isRunning ? 'EXECUTING' : 'STANDBY'}
                              </span>
                            </div>
                            <div className="text-[9px] text-[#7C8091] leading-tight">Worker Engine</div>
                          </div>
                        </div>

                        {/* Zeno Observer Sentinel */}
                        <div className="flex items-center gap-2 rounded-lg border border-[#818CF8]/30 bg-[#18162E]/80 px-3 py-1.5 backdrop-blur-xs">
                          <ShieldCheck className="h-4 w-4 text-[#A5B4FC]" />
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[11px] font-bold text-[#E6E8EE]">Zeno Observer</span>
                              <span className="text-[9px] px-1.5 py-0.2 rounded font-mono font-semibold bg-[#818CF8]/20 text-[#C7D2FE] border border-[#818CF8]/40">
                                ACTIVE GUARD
                              </span>
                            </div>
                            <div className="text-[9px] text-[#7C8091] leading-tight">
                              OS Shield Armed · Roaming Active
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Center: Mission Progress Bar */}
                      <div className="flex-1 max-w-md mx-2 min-w-[200px]">
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="font-semibold text-[#CBD5E1] truncate flex items-center gap-1.5">
                            <Sparkles className="h-3 w-3 text-[#3B82F6]" />
                            {totalStepsCount > 0
                              ? `Milestone ${Math.min(currentStepIdx + 1, totalStepsCount)} of ${totalStepsCount}`
                              : 'Autonomous Task Roadmap'}
                          </span>
                          <span className="font-mono text-[10px] font-bold text-[#93C5FD]">
                            {progressPercent}% Complete
                          </span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-[#1A1A24] overflow-hidden border border-[#262636]">
                          <div
                            className="h-full bg-gradient-to-r from-[#3B82F6] via-[#6366F1] to-[#10B981] transition-all duration-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.5)]"
                            style={{ width: `${progressPercent}%` }}
                          />
                        </div>
                      </div>

                      {/* Right: Telemetry & Actions */}
                      <div className="flex items-center gap-2">
                        <div
                          className="hidden md:flex items-center gap-1.5 rounded-md border border-[#22222A] bg-[#121217] px-2.5 py-1 text-[10px] font-mono text-[#7C8091]"
                          title={defaultWorkspace}
                        >
                          <FolderOpen className="h-3 w-3 text-[#38BDF8]" />
                          <span className="text-[#CBD5E1] truncate max-w-[140px]">
                            {defaultWorkspace.split('\\').pop() || defaultWorkspace.split('/').pop() || 'Workspace'}
                          </span>
                        </div>

                        <button
                          onClick={() =>
                            updateSessionAgent(activeSessionId, () => ({
                              hasTask: false,
                              status: 'standby',
                              plan: null,
                              scratchpad: [],
                              thoughts: [],
                              workspaceFiles: [],
                              messages: [],
                            }))
                          }
                          className="flex items-center gap-1 rounded-md border border-[#22222A] bg-[#14141B] px-2.5 py-1 text-[11px] font-medium text-[#7C8091] hover:text-[#E6E8EE] hover:border-[#333342] transition-colors cursor-pointer"
                          title="Return to Standby"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Reset
                        </button>
                      </div>
                    </div>

                    {/* MAIN 3-COLUMN WORKSPACE BODY */}
                    <div className="flex flex-1 overflow-hidden">
                      {/* Left Column: Detailed Roadmap & Step Checklist */}
                      <div className="w-[320px] border-r border-[#1E1E28] bg-[#0D0D12] p-3.5 flex flex-col shrink-0">
                        <div className="mb-3 flex items-center justify-between pb-2 border-b border-[#1E1E28]">
                          <span className="text-xs font-bold text-[#E6E8EE] flex items-center gap-1.5 tracking-wide">
                            <Sparkles className="h-3.5 w-3.5 text-[#3B82F6]" />
                            Engineering Roadmap
                          </span>
                          <span className="text-[10px] font-mono rounded bg-[#181824] px-2 py-0.5 font-bold text-[#93C5FD] border border-[#252538]">
                            {completedStepsCount} / {totalStepsCount} Done
                          </span>
                        </div>

                        <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                          {planSteps.length === 0 ? (
                            <div className="py-8 text-center text-[#7C8091] text-xs">
                              <Clock className="h-6 w-6 mx-auto mb-2 opacity-30 text-[#3B82F6]" />
                              <div>No milestones generated yet. Provide an instruction below to plan.</div>
                            </div>
                          ) : (
                            planSteps.map((st, idx) => {
                              const isCompleted = st.completed;
                              const isActive = idx === currentStepIdx && !isCompleted;
                              return (
                                <div
                                  key={idx}
                                  className={`rounded-lg p-2.5 text-xs transition-all relative ${
                                    isCompleted
                                      ? 'border border-[#10B981]/30 bg-[#0B1A12]/80 text-[#34D399]'
                                      : isActive
                                      ? 'border border-[#3B82F6] bg-[#0F1D38] text-[#93C5FD] shadow-md shadow-blue-950/40 ring-1 ring-[#3B82F6]/40'
                                      : 'border border-[#1E1E28] bg-[#121218] text-[#7C8091] hover:border-[#2A2A3A]'
                                  }`}
                                >
                                  <div className="flex items-center justify-between mb-1.5">
                                    <div className="flex items-center gap-1.5">
                                      {isCompleted ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-[#10B981] shrink-0" />
                                      ) : isActive ? (
                                        <Activity className="h-3.5 w-3.5 text-[#3B82F6] animate-spin shrink-0" />
                                      ) : (
                                        <span className="h-2 w-2 rounded-full bg-[#3F3F4E] shrink-0 ml-0.5" />
                                      )}
                                      <span className="font-mono text-[10px] font-bold tracking-wider uppercase">
                                        Phase {String(idx + 1).padStart(2, '0')}
                                      </span>
                                    </div>

                                    <span
                                      className={`text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded ${
                                        isCompleted
                                          ? 'bg-[#10B981]/20 text-[#6EE7B7]'
                                          : isActive
                                          ? 'bg-[#3B82F6]/30 text-[#BFDBFE] animate-pulse'
                                          : 'bg-[#1A1A24] text-[#636674]'
                                      }`}
                                    >
                                      {isCompleted ? 'COMPLETED' : isActive ? 'EXECUTING' : 'QUEUED'}
                                    </span>
                                  </div>

                                  <div className="text-[11px] leading-relaxed font-medium pl-5">{st.text}</div>
                                </div>
                              );
                            })
                          )}
                        </div>

                        {/* Roadmap Scope Footer */}
                        <div className="mt-3 border-t border-[#1E1E28] pt-2.5 text-[10px] space-y-1">
                          <div className="flex items-center justify-between text-[#7C8091]">
                            <span>Observer Guard:</span>
                            <span className="font-semibold text-[#A5B4FC]">Enforced</span>
                          </div>
                          <div className="flex items-center justify-between text-[#7C8091]">
                            <span>Roaming Authority:</span>
                            <span className="font-semibold text-[#34D399]">Full User Root</span>
                          </div>
                        </div>
                      </div>

                      {/* Center Column: Execution Engine & Telemetry Console */}
                      <div className="flex-1 flex flex-col overflow-hidden bg-[#08080C]">
                        {/* Live Active Directive Focus Header */}
                        <div className="border-b border-[#1E1E28] bg-[#0E0E14] px-4 py-3 flex items-center justify-between gap-3 shrink-0">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="rounded-md bg-[#1E293B] p-1.5 text-[#38BDF8] shrink-0 border border-[#334155]">
                              <Terminal className="h-4 w-4" />
                            </div>
                            <div className="min-w-0">
                              <div className="text-[10px] font-mono text-[#7C8091] uppercase tracking-wider">
                                {isRunning ? 'Live Directive Under Execution' : 'Autonomous Execution Console'}
                              </div>
                              <div className="text-xs font-semibold text-[#E6E8EE] truncate">
                                {currentActiveStep}
                              </div>
                            </div>
                          </div>

                          {isRunning && (
                            <div className="flex items-center gap-2 rounded-full border border-[#3B82F6]/40 bg-[#1E3A8A]/30 px-3 py-1 text-[11px] text-[#93C5FD] shrink-0">
                              <Activity className="h-3.5 w-3.5 animate-spin text-[#3B82F6]" />
                              <span className="font-medium">Active</span>
                            </div>
                          )}
                        </div>

                        {/* Neural Canvas & Live Thought Ticker */}
                        <div className="relative h-28 border-b border-[#1E1E28] overflow-hidden bg-[#09090F] shrink-0">
                          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full opacity-60" />
                          <div className="absolute inset-0 bg-gradient-to-t from-[#08080C] via-transparent to-transparent" />
                          <div className="absolute top-2.5 left-4 flex items-center gap-1.5 text-[11px] font-semibold text-[#60A5FA]">
                            <BrainCircuit className="h-3.5 w-3.5" />
                            Neural Reasoning Matrix
                          </div>

                          {/* Floating Monologue Thoughts */}
                          <div className="absolute bottom-2 left-4 right-4 flex flex-col gap-1">
                            {activeAgentState.thoughts.slice(0, 2).map((thought, idx) => (
                              <div
                                key={idx}
                                className="rounded-md bg-[#12121A]/90 backdrop-blur-xs border border-[#3B82F6]/30 px-2.5 py-1 text-[11px] text-[#CBD5E1] shadow-md flex items-center gap-2 font-mono truncate"
                              >
                                <span className="h-1.5 w-1.5 rounded-full bg-[#3B82F6] animate-ping shrink-0" />
                                <span className="truncate">{thought}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Execution Feed & Scratchpad Scrollable Area */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                          {/* Working Memory Scratchpad */}
                          {activeAgentState.scratchpad.length > 0 && (
                            <div className="rounded-lg border border-[#1E1E28] bg-[#0E0E14] p-3 shadow-xs">
                              <div className="text-[11px] font-bold text-[#E6E8EE] mb-2 flex items-center gap-2">
                                <FileText className="h-3.5 w-3.5 text-[#3B82F6]" />
                                Working Memory Scratchpad
                              </div>
                              <div className="space-y-1 font-mono text-[11px] text-[#CBD5E1]">
                                {activeAgentState.scratchpad.map((note, idx) => (
                                  <div
                                    key={idx}
                                    className="flex items-start gap-2 bg-[#09090D] p-1.5 rounded border border-[#1A1A24]"
                                  >
                                    <span className="text-[#3B82F6] font-bold">&gt;</span>
                                    <span className="break-words">{note}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Screen Captures / Verifications */}
                          {activeAgentState.screenshots && activeAgentState.screenshots.length > 0 && (
                            <div className="rounded-lg border border-[#1E1E28] bg-[#0E0E14] p-3 shadow-xs">
                              <div className="text-[11px] font-bold text-[#E6E8EE] mb-2 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <Monitor className="h-3.5 w-3.5 text-[#38BDF8]" />
                                  <span>Visual Verifications ({activeAgentState.screenshots.length})</span>
                                </div>
                                <span className="text-[10px] text-[#7C8091]">Click to expand</span>
                              </div>
                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                {activeAgentState.screenshots.map((shot, sIdx) => (
                                  <div
                                    key={sIdx}
                                    onClick={() => setZoomedImage(shot.base64)}
                                    className="group relative cursor-pointer overflow-hidden rounded-md border border-[#22222A] bg-[#0A0A0C] hover:border-[#3B82F6] transition-all"
                                  >
                                    <img
                                      src={shot.base64}
                                      alt={shot.name}
                                      className="h-24 w-full object-cover group-hover:scale-105 transition-transform"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent flex flex-col justify-end p-1.5 opacity-90 group-hover:opacity-100 transition-opacity">
                                      <span className="text-[10px] font-semibold text-[#E6E8EE] truncate">
                                        {shot.stepTitle || shot.name}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Message & Tool Execution Stream */}
                          <div className="space-y-3">
                            {(activeAgentState.messages || []).length === 0 ? (
                              <div className="py-10 text-center text-[#7C8091] text-xs">
                                <Bot className="h-7 w-7 mx-auto mb-2 opacity-30 text-[#3B82F6]" />
                                <div className="font-medium text-[#CBD5E1]">Autonomous Agent Ready</div>
                                <div className="text-[11px] mt-1 text-[#64748B]">
                                  Instruct Zeno below or select a preset task to start execution.
                                </div>
                              </div>
                            ) : (
                              (activeAgentState.messages || []).map((msg) => (
                                <div key={msg.id} className="text-xs">
                                  <div className="flex items-center gap-1.5 mb-1">
                                    {msg.role === 'assistant' ? (
                                      <>
                                        <ZenoLogo size={14} glow />
                                        <span className="font-bold text-[#93C5FD]">Zeno Builder</span>
                                      </>
                                    ) : msg.role === 'tool' ? (
                                      <div className="flex items-center gap-1 text-[#38BDF8] font-mono text-[11px]">
                                        <Terminal className="h-3 w-3" />
                                        <span className="font-bold">Tool Execution</span>
                                      </div>
                                    ) : (
                                      <span className="font-bold text-[#7C8091]">
                                        {msg.role === 'user' ? 'Operator' : 'System'}
                                      </span>
                                    )}
                                    <span className="text-[10px] text-[#555566] font-mono ml-auto">
                                      {msg.timestamp}
                                    </span>
                                  </div>
                                  <div className="mt-1 text-[#E6E8EE]">
                                    {renderMessageContent(msg.content, msg.isStreaming)}
                                  </div>
                                </div>
                              ))
                            )}

                            {/* Live Running Indicator */}
                            {isRunning && (
                              <div className="rounded-lg border border-[#3B82F6]/40 bg-[#172554]/30 p-3 text-xs text-[#93C5FD] flex items-center gap-3">
                                <Activity className="h-4 w-4 animate-spin text-[#3B82F6] shrink-0" />
                                <div>
                                  <div className="font-semibold text-[#E6E8EE]">
                                    {currentStepText || 'Agent is executing milestone...'}
                                  </div>
                                  <div className="text-[11px] text-[#7C8091] mt-0.5">
                                    {nextStepText || 'Invoking native tools and verifying filesystem outputs...'}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Interactive Agent Command Deck (Bottom Input) */}
                        <div className="border-t border-[#1E1E28] p-3 bg-[#0D0D13] shrink-0">
                          {/* Quick Suggestion Chips */}
                          <div className="flex items-center gap-1.5 mb-2 overflow-x-auto pb-1 text-[10px]">
                            <button
                              onClick={() =>
                                setInputText(
                                  'Execute run_tests to verify zero regressions across all unit tests and report output.'
                                )
                              }
                              className="rounded bg-[#171722] hover:bg-[#20202F] text-[#93C5FD] border border-[#252538] px-2 py-0.5 whitespace-nowrap cursor-pointer transition-colors"
                            >
                              Run Unit Test Suite
                            </button>
                            <button
                              onClick={() =>
                                setInputText(
                                  'Scaffold modular directory architecture with manifest files and type definitions.'
                                )
                              }
                              className="rounded bg-[#171722] hover:bg-[#20202F] text-[#93C5FD] border border-[#252538] px-2 py-0.5 whitespace-nowrap cursor-pointer transition-colors"
                            >
                              Scaffold Architecture
                            </button>
                            <button
                              onClick={() =>
                                setInputText(
                                  'Conduct security audit of all modified files and generate executive markdown report.'
                                )
                              }
                              className="rounded bg-[#171722] hover:bg-[#20202F] text-[#93C5FD] border border-[#252538] px-2 py-0.5 whitespace-nowrap cursor-pointer transition-colors"
                            >
                              Security Audit & Report
                            </button>
                          </div>

                          <div className="flex items-center rounded-lg border border-[#22222E] bg-[#14141B] p-2 focus-within:border-[#3B82F6]">
                            <textarea
                              value={inputText}
                              onChange={(e) => setInputText(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                  e.preventDefault();
                                  executeTurn(inputText);
                                }
                              }}
                              placeholder="Instruct Zeno Builder on this workspace (Observer will review actions)..."
                              rows={1}
                              className="flex-1 resize-none bg-transparent px-2 text-xs text-[#E6E8EE] placeholder-[#64748B] outline-none"
                            />
                            <button
                              onClick={() => executeTurn(inputText)}
                              disabled={!inputText.trim()}
                              className="flex items-center gap-1.5 rounded-md bg-[#3B82F6] px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-40 cursor-pointer hover:bg-[#2563EB] transition-colors"
                            >
                              <Terminal className="h-3 w-3" />
                              Instruct
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Right Column: 3-Tab Ops Center (Files, Observer Sentinel, Active Jobs) */}
                      <div className="w-[320px] border-l border-[#1E1E28] bg-[#0D0D12] p-3 flex flex-col shrink-0">
                        {/* Tab Headers */}
                        <div className="flex items-center gap-1 mb-3 border-b border-[#1E1E28] pb-2 text-[11px] font-semibold">
                          <button
                            onClick={() => setRightColTab('files')}
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                              rightColTab === 'files'
                                ? 'bg-[#172554] text-[#93C5FD] border border-[#1E3A8A]'
                                : 'text-[#7C8091] hover:text-[#E6E8EE]'
                            }`}
                          >
                            <FolderOpen className="h-3.5 w-3.5" />
                            Files ({activeAgentState.workspaceFiles.length})
                          </button>
                          <button
                            onClick={() => setRightColTab('observer')}
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                              rightColTab === 'observer'
                                ? 'bg-[#1E1B4B] text-[#A5B4FC] border border-[#312E81]'
                                : 'text-[#7C8091] hover:text-[#E6E8EE]'
                            }`}
                          >
                            <ShieldCheck className="h-3.5 w-3.5 text-[#818CF8]" />
                            Observer
                            {observerDialogues.some((d) => d.verdict === 'vetoed') && (
                              <span className="h-1.5 w-1.5 rounded-full bg-[#EF4444]" />
                            )}
                          </button>
                          <button
                            onClick={() => setRightColTab('jobs')}
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                              rightColTab === 'jobs'
                                ? 'bg-[#064E3B] text-[#6EE7B7] border border-[#047857]'
                                : 'text-[#7C8091] hover:text-[#E6E8EE]'
                            }`}
                          >
                            <Terminal className="h-3.5 w-3.5 text-[#34D399]" />
                            Jobs ({activeJobs.length})
                          </button>
                        </div>

                        {/* Pending Approvals Urgent Callout */}
                        {pendingApprovals.length > 0 && (
                          <div className="mb-3 space-y-2">
                            {pendingApprovals.map((app) => (
                              <div
                                key={app.approval_id}
                                className="rounded-lg border border-[#F59E0B]/50 bg-[#78350F]/20 p-2.5 text-xs text-[#E6E8EE]"
                              >
                                <div className="flex items-center justify-between text-[11px] font-bold text-[#FBBF24] mb-1">
                                  <span className="flex items-center gap-1">
                                    <AlertTriangle className="h-3.5 w-3.5 text-[#F59E0B]" />
                                    Operator Approval Required
                                  </span>
                                  <span className="font-mono text-[9px] text-[#FDE68A]">{app.action_type}</span>
                                </div>
                                <div className="text-[11px] text-[#E6E8EE] mb-2 leading-tight">{app.summary}</div>
                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={() => handleDecideApproval(app.approval_id, true)}
                                    className="rounded bg-[#4ADE80] px-2.5 py-0.5 text-[10px] font-semibold text-black hover:bg-[#22C55E] cursor-pointer"
                                  >
                                    Approve
                                  </button>
                                  <button
                                    onClick={() => handleDecideApproval(app.approval_id, false)}
                                    className="rounded bg-[#EF4444] px-2.5 py-0.5 text-[10px] font-semibold text-white hover:bg-[#DC2626] cursor-pointer"
                                  >
                                    Reject
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Tab 1: Files */}
                        {rightColTab === 'files' && (
                          <div className="space-y-1.5 flex-1 overflow-y-auto">
                            {activeAgentState.workspaceFiles.length === 0 ? (
                              <div className="py-8 text-center text-[11px] text-[#7C8091]">
                                <FolderOpen className="h-6 w-6 mx-auto mb-1.5 opacity-30 text-[#3B82F6]" />
                                <div>No files created in workspace yet</div>
                              </div>
                            ) : (
                              activeAgentState.workspaceFiles.map((wf, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between rounded-md border border-[#1E1E28] bg-[#14141B] p-2 text-xs hover:border-[#2E2E3E] transition-colors"
                                >
                                  <div className="flex items-center gap-2 truncate">
                                    {wf.type === 'code' ? (
                                      <FileCode className="h-3.5 w-3.5 text-[#3B82F6] shrink-0" />
                                    ) : wf.type === 'image' ? (
                                      <ImageIcon className="h-3.5 w-3.5 text-[#4ADE80] shrink-0" />
                                    ) : (
                                      <FileText className="h-3.5 w-3.5 text-[#EAB308] shrink-0" />
                                    )}
                                    <span className="truncate text-[#E6E8EE] text-[11px] font-mono">{wf.name}</span>
                                  </div>
                                  <span className="text-[10px] text-[#7C8091] font-mono shrink-0 ml-2">{wf.size}</span>
                                </div>
                              ))
                            )}
                          </div>
                        )}

                        {/* Tab 2: Observer Sentinel Ledger */}
                        {rightColTab === 'observer' && (
                          <div className="space-y-2 flex-1 overflow-y-auto pr-0.5">
                            <div className="rounded-lg border border-[#818CF8]/30 bg-[#1E1B4B]/20 p-2.5 text-[11px]">
                              <div className="flex items-center gap-1.5 font-bold text-[#A5B4FC] mb-1">
                                <ShieldCheck className="h-4 w-4 text-[#818CF8]" />
                                Dual-Agent Sentinel Ledger
                              </div>
                              <div className="text-[10px] text-[#CBD5E1] leading-relaxed">
                                <strong className="text-[#93C5FD]">Zeno Builder</strong> executes milestones while{' '}
                                <strong className="text-[#A5B4FC]">Zeno Observer</strong> audits every action in real
                                time against destructive operations.
                              </div>
                            </div>

                            {observerDialogues.length === 0 ? (
                              <div className="py-8 text-center text-[11px] text-[#7C8091]">
                                <ShieldCheck className="h-6 w-6 mx-auto mb-1.5 opacity-30 text-[#818CF8]" />
                                <div>No safety audits recorded yet</div>
                              </div>
                            ) : (
                              observerDialogues.map((dlg) => (
                                <div
                                  key={dlg.dialogue_id}
                                  className={`rounded-lg border p-2 text-xs ${
                                    dlg.verdict === 'vetoed'
                                      ? 'border-[#EF4444]/50 bg-[#450A0A]/40 text-[#FCA5A5]'
                                      : 'border-[#1E1E28] bg-[#14141B] text-[#CBD5E1]'
                                  }`}
                                >
                                  <div className="flex items-center justify-between text-[10px] mb-1">
                                    <span className="font-semibold text-[#E6E8EE] flex items-center gap-1">
                                      {dlg.verdict === 'vetoed' ? (
                                        <ShieldAlert className="h-3 w-3 text-[#EF4444]" />
                                      ) : (
                                        <Check className="h-3 w-3 text-[#4ADE80]" />
                                      )}
                                      {dlg.speaker === 'Zeno Observer' ? 'Observer Sentinel' : 'Builder Directive'}
                                    </span>
                                    <span className="text-[9px] text-[#7C8091] font-mono">{dlg.action_type || 'audit'}</span>
                                  </div>
                                  <div className="text-[11px] leading-tight font-mono text-[#E6E8EE] break-words">
                                    {dlg.message}
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        )}

                        {/* Tab 3: Background Jobs */}
                        {rightColTab === 'jobs' && (
                          <div className="space-y-2 flex-1 overflow-y-auto">
                            {activeJobs.length === 0 ? (
                              <div className="py-8 text-center text-[11px] text-[#7C8091]">
                                <Terminal className="h-6 w-6 mx-auto mb-1.5 opacity-30 text-[#34D399]" />
                                <div>No background jobs running</div>
                              </div>
                            ) : (
                              activeJobs.map((jb) => (
                                <div
                                  key={jb.job_id}
                                  className="rounded-lg border border-[#1E1E28] bg-[#14141B] p-2.5 text-xs text-[#E6E8EE]"
                                >
                                  <div className="flex items-center justify-between text-[11px] mb-1">
                                    <span className="font-bold text-[#34D399] flex items-center gap-1">
                                      <Activity className="h-3 w-3 animate-spin text-[#34D399]" />
                                      {jb.command_type}
                                    </span>
                                    <span className="font-mono text-[9px] text-[#7C8091]">{jb.job_id.slice(0, 8)}</span>
                                  </div>
                                  <div className="text-[10px] text-[#CBD5E1] truncate font-mono mb-2">
                                    {jb.command_args ? jb.command_args.join(' ') : 'running...'}
                                  </div>
                                  <button
                                    onClick={() => handleCancelJob(jb.job_id)}
                                    className="rounded bg-[#EF4444]/20 border border-[#EF4444]/40 px-2.5 py-0.5 text-[10px] text-[#FCA5A5] hover:bg-[#EF4444]/30 cursor-pointer"
                                  >
                                    Cancel Job
                                  </button>
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })()
            )
          ) : (
            /* CHAT ASSISTANT CONVERSATIONAL STREAM */
            <div className="flex flex-1 flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                {availableModels.length === 0 && (
                  <div className="rounded border border-[#F87171]/40 bg-[#F87171]/10 p-3.5 text-xs text-[#E6E8EE]">
                    <div className="flex items-center gap-2 font-semibold text-[#F87171] mb-1">
                      <AlertTriangle className="h-4 w-4" />
                      API Key Required
                    </div>
                    <p className="text-[11px] text-[#CBD5E1] mb-2.5">
                      Zeno does not include hardcoded API keys and requires a key to connect to AI models. Select your provider (Gemini, Claude, OpenRouter, OpenAI, Groq) in Settings and input your key.
                    </p>
                    <button
                      onClick={() => setIsSettingsOpen(true)}
                      className="rounded bg-[#3B82F6] px-3 py-1 text-xs font-semibold text-white hover:bg-[#2563EB]"
                    >
                      Open Settings &amp; Configure Key
                    </button>
                  </div>
                )}
                {/* Auto Compaction Suggestion Banner */}
                {activeSession.messages.length >= 10 &&
                  !activeSession.messages.some((m) => m.isCompactedMemory) &&
                  dismissedCompactNoticeId !== activeSession.id && (
                    <div className="flex items-center justify-between rounded-lg border border-[#3B82F6]/30 bg-[#172554]/30 px-3.5 py-2 text-xs">
                      <div className="flex items-center gap-2 text-[#93C5FD]">
                        <Sparkles className="h-4 w-4 text-[#38BDF8] shrink-0 animate-pulse" />
                        <span>
                          Conversation is growing long ({activeSession.messages.length} turns). Compact older context to reduce token usage and keep responses lightning fast.
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={handleCompactChat}
                          disabled={isCompacting}
                          className="flex items-center gap-1.5 rounded bg-[#3B82F6] px-2.5 py-1 text-xs font-semibold text-white hover:bg-[#2563EB] cursor-pointer"
                        >
                          <Sparkles className="h-3 w-3" />
                          {isCompacting ? 'Compacting...' : 'Compact Now'}
                        </button>
                        <button
                          onClick={() => setDismissedCompactNoticeId(activeSession.id)}
                          className="text-[11px] text-[#7C8091] hover:text-[#E6E8EE]"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  )}

                {activeSession.messages.map((msg) => {
                  if (msg.isCompactedMemory) {
                    const isExpanded = expandedMemoryIds.has(msg.id);
                    return (
                      <div key={msg.id} className="my-2 rounded-lg border border-[#3B82F6]/40 bg-[#0F172A]/70 p-3 shadow-md">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex h-6 w-6 items-center justify-center rounded bg-[#3B82F6]/20 border border-[#3B82F6]/40">
                              <Sparkles className="h-3.5 w-3.5 text-[#38BDF8]" />
                            </div>
                            <div>
                              <div className="text-xs font-semibold text-[#93C5FD] flex items-center gap-1.5">
                                Context Window Compacted
                                <span className="rounded bg-[#1E293B] px-1.5 py-0.2 text-[10px] text-[#4ADE80] font-mono border border-[#334155]/60">
                                  Saved ~{msg.savedTokens || 800} tokens
                                </span>
                              </div>
                              <div className="text-[10px] text-[#7C8091]">
                                {msg.archivedCount || 0} older turns distilled into high-density memory • Recent turns preserved verbatim
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {msg.archivedMessages && msg.archivedMessages.length > 0 && (
                              <button
                                onClick={() => setArchivedModalMessages(msg.archivedMessages || null)}
                                className="rounded px-2 py-1 text-[11px] text-[#7C8091] hover:text-[#E6E8EE] hover:bg-[#1E293B] transition-colors cursor-pointer"
                              >
                                View Archived Turns ({msg.archivedCount})
                              </button>
                            )}
                            <button
                              onClick={() => toggleMemoryExpanded(msg.id)}
                              className="flex items-center gap-1 rounded bg-[#1E293B] hover:bg-[#283548] px-2.5 py-1 text-xs font-medium text-[#93C5FD] border border-[#3B82F6]/30 transition-colors cursor-pointer"
                            >
                              <Eye className="h-3 w-3" />
                              {isExpanded ? 'Collapse Memory' : 'Inspect Memory'}
                            </button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-3 pt-3 border-t border-[#3B82F6]/20 text-xs text-[#CBD5E1]">
                            {renderMessageContent(msg.content)}
                          </div>
                        )}
                      </div>
                    );
                  }

                  if (msg.role === 'system') {
                    if (msg.id === 'welcome' && activeSession.messages.length === 1) {
                      return (
                        <div key={msg.id} className="py-8 flex flex-col items-center justify-center text-center">
                          <div className="relative mb-3 flex items-center justify-center">
                            <div className="absolute inset-0 rounded-full bg-[#3B82F6]/20 blur-xl animate-pulse" />
                            <ZenoLogo size={56} glow pulse />
                          </div>
                          <h2 className="text-lg font-bold text-[#FFFFFF] mb-1">Zeno Desktop AI Assistant</h2>
                          <p className="text-xs text-[#7C8091] max-w-md mb-6 leading-relaxed">
                            Autonomous neural workspace &amp; native desktop copilot. Ask questions, explore code, execute safe scripts, or delegate milestones.
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg text-left">
                            <button
                              onClick={() => executeTurn('/sys')}
                              className="rounded-lg border border-[#22222A] bg-[#111115] hover:border-[#3B82F6]/60 p-3 text-xs transition-colors cursor-pointer group"
                            >
                              <div className="font-semibold text-[#E6E8EE] group-hover:text-[#93C5FD] flex items-center gap-1.5 mb-1">
                                <Cpu className="h-3.5 w-3.5 text-[#3B82F6]" />
                                System Telemetry
                              </div>
                              <div className="text-[11px] text-[#7C8091]">Read CPU, RAM, battery, and OS diagnostics</div>
                            </button>
                            <button
                              onClick={() => executeTurn('List files in the current workspace and explain the structure')}
                              className="rounded-lg border border-[#22222A] bg-[#111115] hover:border-[#3B82F6]/60 p-3 text-xs transition-colors cursor-pointer group"
                            >
                              <div className="font-semibold text-[#E6E8EE] group-hover:text-[#93C5FD] flex items-center gap-1.5 mb-1">
                                <FolderOpen className="h-3.5 w-3.5 text-[#3B82F6]" />
                                Inspect Workspace Files
                              </div>
                              <div className="text-[11px] text-[#7C8091]">Explore directories, scripts, and documents</div>
                            </button>
                            <button
                              onClick={() => executeTurn('Write a python script to test file operations')}
                              className="rounded-lg border border-[#22222A] bg-[#111115] hover:border-[#3B82F6]/60 p-3 text-xs transition-colors cursor-pointer group"
                            >
                              <div className="font-semibold text-[#E6E8EE] group-hover:text-[#93C5FD] flex items-center gap-1.5 mb-1">
                                <FileCode className="h-3.5 w-3.5 text-[#4ADE80]" />
                                Python Execution
                              </div>
                              <div className="text-[11px] text-[#7C8091]">Run isolated code in a safe subprocess</div>
                            </button>
                            <button
                              onClick={() => executeTurn('/search modern web application best practices')}
                              className="rounded-lg border border-[#22222A] bg-[#111115] hover:border-[#3B82F6]/60 p-3 text-xs transition-colors cursor-pointer group"
                            >
                              <div className="font-semibold text-[#E6E8EE] group-hover:text-[#93C5FD] flex items-center gap-1.5 mb-1">
                                <Globe className="h-3.5 w-3.5 text-[#EAB308]" />
                                Web Documentation Search
                              </div>
                              <div className="text-[11px] text-[#7C8091]">Fetch live technical documentation</div>
                            </button>
                          </div>
                        </div>
                      );
                    }
                    return (
                      <div key={msg.id} className="text-center text-xs text-[#7C8091] py-2">
                        {msg.content}
                      </div>
                    );
                  }

                  if (msg.role === 'tool') {
                    return (
                      <div key={msg.id} className="text-xs text-[#7C8091] py-1 font-mono">
                        {msg.content}
                      </div>
                    );
                  }

                  if (msg.role === 'user') {
                    return (
                      <div key={msg.id} className="group relative flex flex-col items-end">
                        <div className="flex items-center gap-2 mb-1 mr-1">
                          <button
                            onClick={() => handleRetryTurn(msg)}
                            disabled={isRunning}
                            title="Edit / Retry this prompt"
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-[#7C8091] hover:text-[#93C5FD] hover:bg-[#1E293B] cursor-pointer"
                          >
                            <RotateCcw className="h-3 w-3" />
                          </button>
                          <span className="text-[11px] text-[#7C8091]">You</span>
                        </div>
                        {/* Render attached files chips */}
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div className="mb-2 flex flex-wrap gap-2 justify-end">
                            {msg.attachments.map((att) => (
                              <div
                                key={att.id}
                                className="flex items-center gap-1.5 rounded border border-[#22222A] bg-[#17171D] p-1.5 text-xs text-[#CBD5E1]"
                              >
                                {att.type.startsWith('image/') && att.base64 ? (
                                  <img
                                    src={att.base64}
                                    alt={att.name}
                                    onClick={() => setZoomedImage(att.base64!)}
                                    className="h-8 w-8 rounded object-cover cursor-pointer hover:opacity-80 transition-opacity"
                                  />
                                ) : att.type === 'text/code' ? (
                                  <FileCode className="h-4 w-4 text-[#4ADE80]" />
                                ) : (
                                  <FileText className="h-4 w-4 text-[#3B82F6]" />
                                )}
                                <span className="max-w-[140px] truncate text-[11px]">{att.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="max-w-[75%] rounded-md border border-[#1E3A8A] bg-[#131C35] px-4 py-2.5 text-xs text-[#E6E8EE] whitespace-pre-wrap">
                          {msg.content}
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={msg.id} className="group flex flex-col items-start max-w-[85%]">
                      <div className="flex items-center gap-2 mb-1.5">
                        <ZenoLogo size={18} glow />
                        <span className="text-xs font-bold text-[#E6E8EE]">Zeno</span>
                        {activeModel && (
                          <span className="rounded bg-[#17171D] border border-[#22222A] px-1.5 py-0.5 text-[10px] text-[#7C8091] font-mono">
                            {activeModel}
                          </span>
                        )}
                      </div>
                      <div className="w-full text-xs text-[#E6E8EE]">
                        {renderMessageContent(msg.content, msg.isStreaming)}

                        {/* Agent Captured Screenshots Gallery */}
                        {msg.agentScreenshots && msg.agentScreenshots.length > 0 && (
                          <div className="mt-3 rounded-lg border border-[#22222A] bg-[#111116] p-3">
                            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#93C5FD] mb-2">
                              <Eye className="h-3.5 w-3.5 text-[#38BDF8]" />
                              Visual Verification Captures ({msg.agentScreenshots.length})
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {msg.agentScreenshots.map((scr, sIdx) => (
                                <div
                                  key={sIdx}
                                  onClick={() => setZoomedImage(scr.base64)}
                                  className="group/img relative rounded border border-[#22222A] overflow-hidden bg-[#09090C] cursor-pointer hover:border-[#38BDF8] transition-all"
                                >
                                  <img src={scr.base64} alt={scr.name} className="w-full h-24 object-cover" />
                                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 flex items-center justify-center transition-opacity">
                                    <Maximize2 className="h-4 w-4 text-white" />
                                  </div>
                                  <div className="p-1 text-[10px] text-[#7C8091] truncate bg-[#17171D]">
                                    {scr.name}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Message Action Footer: Copy & Regenerate Retry Button */}
                        <div className="mt-2 flex items-center gap-2 text-[11px] text-[#7C8091]">
                          <button
                            onClick={() => handleCopy(msg.content, msg.id)}
                            className="flex items-center gap-1 rounded hover:text-[#E6E8EE] px-1.5 py-0.5 hover:bg-[#1E1E26] cursor-pointer transition-colors"
                            title="Copy response"
                          >
                            {copiedCodeId === msg.id ? (
                              <>
                                <Check className="h-3 w-3 text-[#4ADE80]" />
                                <span className="text-[#4ADE80]">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="h-3 w-3" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                          <button
                            onClick={() => handleRetryTurn(msg)}
                            disabled={isRunning}
                            className="flex items-center gap-1 rounded hover:text-[#93C5FD] px-1.5 py-0.5 hover:bg-[#1E1E26] cursor-pointer transition-colors"
                            title="Regenerate this response"
                          >
                            <RotateCcw className="h-3 w-3" />
                            <span>Retry</span>
                          </button>
                        </div>

                        {/* Delegate Plan to Agent Button */}
                        {msg.planData && !msg.planData.isDelegated && (
                          <div className="mt-4 rounded-md border border-[#3B82F6]/40 bg-[#172554]/40 p-3">
                            <div className="text-xs font-semibold text-[#93C5FD] mb-1">
                              Agentic Task Blueprint Ready
                            </div>
                            <div className="text-[11px] text-[#7C8091] mb-3">
                              This multi-step workflow can run in the dedicated Agentic Workspace with real-time neural thoughts and step progress.
                            </div>
                            <button
                              onClick={() => handleDelegatePlan(msg.planData!)}
                              className="flex items-center gap-1.5 rounded bg-[#3B82F6] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#2563EB]"
                            >
                              <ArrowRight className="h-3.5 w-3.5" />
                              Give Plan to Agent to Work On
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={chatBottomRef} />
              </div>

              {/* Bottom Input Bar with Plus (+) Drop-up Popover & Smart Code Paste */}
              <div className="border-t border-[#22222A] bg-[#0A0A0C] p-4">
                {/* Hidden File Input Elements for Documents and Images */}
                <input
                  ref={docFileInputRef}
                  type="file"
                  multiple
                  accept=".txt,.md,.py,.ts,.tsx,.js,.json,.html,.css,.cpp,.c,.rs,.go,.sql,.csv,.pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <input
                  ref={imageFileInputRef}
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {/* Attached File & Code Snippet Preview Bar */}
                {attachedFiles.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-2">
                    {attachedFiles.map((att) => (
                      <div
                        key={att.id}
                        className={`flex items-center gap-2 rounded border p-1.5 text-xs ${
                          att.type === 'text/code'
                            ? 'border-[#4ADE80]/40 bg-[#0F2318] text-[#86EFAC]'
                            : 'border-[#22222A] bg-[#17171D] text-[#E6E8EE]'
                        }`}
                      >
                        {att.type.startsWith('image/') && att.base64 ? (
                          <img
                            src={att.base64}
                            alt={att.name}
                            onClick={() => setZoomedImage(att.base64!)}
                            className="h-7 w-7 rounded object-cover cursor-pointer hover:opacity-80"
                          />
                        ) : att.type === 'text/code' ? (
                          <FileCode className="h-4 w-4 text-[#4ADE80]" />
                        ) : (
                          <FileText className="h-4 w-4 text-[#3B82F6]" />
                        )}
                        <span className="max-w-[160px] truncate text-[11px] font-medium">{att.name}</span>
                        {att.size && (
                          <span className="text-[10px] text-[#7C8091] font-mono">({att.size})</span>
                        )}
                        {att.type === 'text/code' && att.content && (
                          <button
                            type="button"
                            onClick={() => {
                              setInputText((prev) => (prev ? `${prev}\n${att.content}` : att.content || ''));
                              removeAttachment(att.id);
                            }}
                            title="Convert snippet to inline text in input"
                            className="rounded px-1.5 py-0.5 text-[10px] text-[#7C8091] hover:text-[#93C5FD] hover:bg-[#22222E] cursor-pointer"
                          >
                            Inline text
                          </button>
                        )}
                        <button
                          onClick={() => removeAttachment(att.id)}
                          className="rounded p-0.5 text-[#7C8091] hover:text-[#F87171]"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex rounded-md border border-[#22222A] bg-[#17171D] p-2 focus-within:border-[#3B82F6]">
                  {/* Plus (+) Drop-up Popover Menu */}
                  <div className="relative flex items-center pr-2" ref={plusMenuRef}>
                    <button
                      onClick={() => setIsPlusMenuOpen((prev) => !prev)}
                      title="Attach documents, images, window captures, or clipboard"
                      className={`flex h-8 w-8 items-center justify-center rounded transition-colors ${
                        isPlusMenuOpen
                          ? 'bg-[#3B82F6] text-white shadow-md shadow-[#3B82F6]/30'
                          : 'bg-[#22222E] text-[#E6E8EE] hover:bg-[#2A2A38]'
                      }`}
                    >
                      <Plus className={`h-4 w-4 transition-transform duration-200 ${isPlusMenuOpen ? 'rotate-45' : ''}`} />
                    </button>

                    {/* Popover Menu: strictly Lucide vector icons, NO emojis */}
                    {isPlusMenuOpen && (
                      <div className="absolute bottom-10 left-0 z-50 w-64 rounded-xl border border-[#2A2A38] bg-[#121218] p-1.5 shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-150">
                        <button
                          onClick={() => {
                            setIsPlusMenuOpen(false);
                            docFileInputRef.current?.click();
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E6E8EE] hover:bg-[#1E1E2A] hover:text-[#93C5FD] transition-colors cursor-pointer text-left"
                        >
                          <FileCode className="h-4 w-4 text-[#4ADE80]" />
                          <div>
                            <div className="font-semibold text-xs">Attach Document / Code</div>
                            <div className="text-[10px] text-[#7C8091]">Scripts, markdown, text, or data files</div>
                          </div>
                        </button>

                        <button
                          onClick={() => {
                            setIsPlusMenuOpen(false);
                            imageFileInputRef.current?.click();
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E6E8EE] hover:bg-[#1E1E2A] hover:text-[#93C5FD] transition-colors cursor-pointer text-left"
                        >
                          <ImageIcon className="h-4 w-4 text-[#38BDF8]" />
                          <div>
                            <div className="font-semibold text-xs">Attach Picture</div>
                            <div className="text-[10px] text-[#7C8091]">PNG, JPG, WebP image files</div>
                          </div>
                        </button>

                        <button
                          onClick={() => {
                            setIsPlusMenuOpen(false);
                            handleOpenTargetPicker();
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E6E8EE] hover:bg-[#1E1E2A] hover:text-[#93C5FD] transition-colors cursor-pointer text-left"
                        >
                          <AppWindow className="h-4 w-4 text-[#A78BFA]" />
                          <div>
                            <div className="font-semibold text-xs">Capture Window or Tab</div>
                            <div className="text-[10px] text-[#7C8091]">Target display, open app, or browser tab</div>
                          </div>
                        </button>

                        <div className="my-1 border-t border-[#22222E]" />

                        <button
                          onClick={() => {
                            setIsPlusMenuOpen(false);
                            handlePasteFromClipboard();
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E6E8EE] hover:bg-[#1E1E2A] hover:text-[#93C5FD] transition-colors cursor-pointer text-left"
                        >
                          <Clipboard className="h-4 w-4 text-[#FACC15]" />
                          <div>
                            <div className="font-semibold text-xs">Paste Clipboard</div>
                            <div className="text-[10px] text-[#7C8091]">Insert copied text or code as a snippet</div>
                          </div>
                        </button>
                      </div>
                    )}
                  </div>

                  <textarea
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onPaste={handleInputPaste}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        executeTurn(inputText);
                      }
                    }}
                    placeholder="Ask Zeno anything, paste code or documents, or click '+' to attach... (Shift+Enter for newline)"
                    rows={Math.min(6, Math.max(2, inputText.split('\n').length))}
                    className="flex-1 resize-none bg-transparent px-2 py-1 text-xs text-[#E6E8EE] placeholder-[#7C8091] outline-none max-h-48"
                  />
                  <div className="flex items-end pl-2">
                    {isRunning ? (
                      <button
                        onClick={handleStop}
                        className="rounded bg-[#F87171] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#EF4444]"
                      >
                        Stop
                      </button>
                    ) : (
                      <button
                        onClick={() => executeTurn(inputText)}
                        disabled={!inputText.trim() && attachedFiles.length === 0}
                        className="rounded bg-[#3B82F6] px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-40 hover:bg-[#2563EB]"
                      >
                        Send
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Status Bar (24px) */}
          <div className="flex h-6 items-center justify-between border-t border-[#22222A] bg-[#111115] px-4 text-[11px] text-[#7C8091]">
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${isRunning ? 'bg-[#3B82F6] animate-pulse' : 'bg-[#4ADE80]'}`} />
              <span>{statusText}</span>
              {isRunning && nextStepText && (
                <span className="text-[#3B82F6] pl-2">| Next: {nextStepText}</span>
              )}
            </div>
            <div>
              Tokens: {tokenCounts.input} in / {tokenCounts.output} out
            </div>
          </div>
        </main>
      </div>

      {/* MODAL: Live Window, Tab & Display Target Picker */}
      {isTargetPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-xl border border-[#22222A] bg-[#111116] shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between border-b border-[#22222A] px-4 py-3 bg-[#17171D]">
              <div className="flex items-center gap-2">
                <AppWindow className="h-4 w-4 text-[#38BDF8]" />
                <h3 className="text-xs font-bold text-[#E6E8EE]">Capture Screen, Window, or Browser Tab</h3>
              </div>
              <button
                onClick={() => setIsTargetPickerOpen(false)}
                className="rounded p-1 text-[#7C8091] hover:text-[#E6E8EE] cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-4 border-b border-[#22222A] bg-[#0E0E12]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#7C8091]" />
                <input
                  type="text"
                  value={targetSearchQuery}
                  onChange={(e) => setTargetSearchQuery(e.target.value)}
                  placeholder="Filter displays, application windows, or browser tabs..."
                  className="w-full rounded-lg border border-[#22222A] bg-[#17171D] pl-9 pr-3 py-2 text-xs text-[#E6E8EE] placeholder-[#7C8091] outline-none focus:border-[#38BDF8]"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {liveScreenTargets
                .filter((tgt) => {
                  if (!targetSearchQuery.trim()) return true;
                  const q = targetSearchQuery.toLowerCase();
                  return (
                    tgt.name.toLowerCase().includes(q) ||
                    (tgt.description && tgt.description.toLowerCase().includes(q))
                  );
                })
                .map((tgt) => (
                  <button
                    key={tgt.id}
                    disabled={isCapturingScreen}
                    onClick={() => handleCaptureSelectedTarget(tgt.id, tgt.name)}
                    className="flex w-full items-center justify-between rounded-lg border border-[#22222A] bg-[#15151B] p-3 text-left hover:border-[#38BDF8] hover:bg-[#1E1E28] transition-all cursor-pointer group disabled:opacity-50"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded bg-[#1F1F2A] group-hover:bg-[#38BDF8]/20 transition-colors">
                        {tgt.type === 'browser_tab' ? (
                          <Globe className="h-4 w-4 text-[#EAB308]" />
                        ) : tgt.type === 'app_window' ? (
                          <AppWindow className="h-4 w-4 text-[#A78BFA]" />
                        ) : (
                          <Monitor className="h-4 w-4 text-[#38BDF8]" />
                        )}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-[#E6E8EE] group-hover:text-[#93C5FD]">
                          {tgt.name}
                        </div>
                        <div className="text-[11px] text-[#7C8091]">
                          {tgt.description || (tgt.type === 'browser_tab' ? 'Browser Window & Tab' : 'Display Surface')}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-[#7C8091] group-hover:text-[#93C5FD]" />
                  </button>
                ))}
            </div>

            <div className="flex items-center justify-between border-t border-[#22222A] px-4 py-3 bg-[#17171D]">
              <span className="text-[11px] text-[#7C8091]">
                {isCapturingScreen ? 'Capturing target frame...' : 'Click any item to capture & attach to input'}
              </span>
              <button
                onClick={() => setIsTargetPickerOpen(false)}
                className="rounded bg-[#22222E] px-3.5 py-1.5 text-xs text-[#E6E8EE] hover:bg-[#2A2A38] cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: Target Screen / Browser Tab Picker (Permission Escalation) */}
      {screenTargetPicker?.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs">
          <div className="w-[500px] rounded border border-[#22222A] bg-[#17171D] p-5 shadow-2xl">
            <h3 className="text-sm font-bold text-[#E6E8EE] mb-2">Select Display or Browser Tab to Attach</h3>
            <p className="text-xs text-[#7C8091] mb-4">
              Choose which screen or browser tab to capture and attach to your input.
            </p>
            <div className="space-y-2 mb-6">
              {[
                { id: 'all', title: 'All Monitors Combined', desc: 'Virtual multi-display canvas' },
                { id: 'monitor_1', title: 'Primary Display', desc: 'Main physical screen' },
                { id: 'browser_tab', title: 'Active Browser Tab', desc: 'Visible browser window with URL and tab bar' },
                { id: 'active_window', title: 'Focused Application Window', desc: 'Active foreground desktop app' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => screenTargetPicker.resolve(opt.id)}
                  className="flex w-full items-center justify-between rounded border border-[#22222A] bg-[#131318] p-3 text-left hover:border-[#3B82F6] hover:bg-[#1A1A24]"
                >
                  <div>
                    <div className="text-xs font-semibold text-[#E6E8EE]">{opt.title}</div>
                    <div className="text-[11px] text-[#7C8091]">{opt.desc}</div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-[#7C8091]" />
                </button>
              ))}
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => screenTargetPicker.resolve('all')}
                className="rounded bg-[#2A2A34] px-4 py-1.5 text-xs text-[#E6E8EE] hover:bg-[#3A3A46]"
              >
                Default (All Monitors)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Permission Request Dialog */}
      {pendingPermission && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs">
          <div className="w-[460px] rounded border border-[#22222A] bg-[#17171D] p-5 shadow-2xl">
            <h3 className="text-sm font-bold text-[#E6E8EE] mb-2">
              Permission Request: {pendingPermission.category}
            </h3>
            <p className="text-xs text-[#7C8091] leading-relaxed mb-6">
              {pendingPermission.description}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => pendingPermission.resolve(false)}
                className="rounded bg-[#2A2A34] px-4 py-1.5 text-xs font-semibold text-[#E6E8EE] hover:bg-[#3A3A46]"
              >
                Deny
              </button>
              <button
                onClick={() => pendingPermission.resolve(true)}
                className="rounded bg-[#3B82F6] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#2563EB]"
              >
                Allow
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Human Safety Review Escalation */}
      {pendingHumanReview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs">
          <div className="w-[520px] rounded border border-[#22222A] bg-[#17171D] p-5 shadow-2xl">
            <div className="flex items-center gap-2 text-[#F87171] mb-2">
              <AlertTriangle className="h-4 w-4" />
              <h3 className="text-sm font-bold">Human Safety Review Required</h3>
            </div>
            <p className="text-xs text-[#E6E8EE] mb-2">
              The AI Safety Guard flagged the following code for human confirmation:
            </p>
            <div className="mb-3 text-[11px] text-[#F87171]">{pendingHumanReview.reason}</div>
            <pre className="mb-6 max-h-40 overflow-y-auto rounded bg-[#0F0F13] p-3 font-mono text-xs text-[#CBD5E1]">
              <code>{pendingHumanReview.code}</code>
            </pre>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => pendingHumanReview.resolve(false)}
                className="rounded bg-[#2A2A34] px-4 py-1.5 text-xs font-semibold text-[#E6E8EE] hover:bg-[#3A3A46]"
              >
                Block Action
              </button>
              <button
                onClick={() => pendingHumanReview.resolve(true)}
                className="rounded bg-[#F87171] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#DC2626]"
              >
                Approve &amp; Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: Archived Compacted Conversation Turns Drawer */}
      {archivedModalMessages && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-xl border border-[#22222A] bg-[#111115] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#22222A] px-4 py-3 bg-[#17171D]">
              <div className="flex items-center gap-2 text-xs font-bold text-[#E6E8EE]">
                <Clock className="h-4 w-4 text-[#3B82F6]" />
                Archived Conversation Turns ({archivedModalMessages.length})
              </div>
              <button
                onClick={() => setArchivedModalMessages(null)}
                className="rounded p-1 text-[#7C8091] hover:text-[#E6E8EE] cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {archivedModalMessages.map((m, idx) => (
                <div key={idx} className="rounded border border-[#22222A] bg-[#0F0F13] p-3 text-xs">
                  <div className="flex items-center justify-between font-bold text-[#7C8091] mb-1">
                    <span>{m.role === 'user' ? 'You' : m.role === 'assistant' ? 'Zeno' : m.role}</span>
                    <span className="font-normal text-[10px]">{m.timestamp}</span>
                  </div>
                  <div className="text-[#CBD5E1] whitespace-pre-wrap leading-relaxed">{m.content}</div>
                </div>
              ))}
            </div>
            <div className="border-t border-[#22222A] px-4 py-2 bg-[#17171D] flex justify-end">
              <button
                onClick={() => setArchivedModalMessages(null)}
                className="rounded bg-[#22222E] px-3.5 py-1 text-xs text-[#E6E8EE] hover:bg-[#2A2A38] cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Compaction Toast Notification */}
      {compactToast && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2.5 rounded-lg border border-[#3B82F6]/60 bg-[#0F172A] px-4 py-2.5 text-xs text-[#E6E8EE] shadow-2xl animate-bounce">
          <Sparkles className="h-4 w-4 text-[#38BDF8]" />
          <span>{compactToast}</span>
        </div>
      )}

      {/* MODAL: Fullscreen Image Lightbox */}
      {zoomedImage && (
        <div
          onClick={() => setZoomedImage(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4 cursor-zoom-out"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative max-w-4xl max-h-[90vh] flex flex-col rounded-xl border border-[#22222A] bg-[#111116] shadow-2xl overflow-hidden cursor-default"
          >
            <div className="flex items-center justify-between border-b border-[#22222A] px-4 py-2 bg-[#17171D]">
              <span className="text-xs font-semibold text-[#E6E8EE]">Image Preview</span>
              <div className="flex items-center gap-2">
                <a
                  href={zoomedImage}
                  download="zeno_capture.png"
                  className="rounded p-1 text-[#7C8091] hover:text-[#93C5FD] transition-colors"
                  title="Download Image"
                >
                  <Download className="h-4 w-4" />
                </a>
                <button
                  onClick={() => setZoomedImage(null)}
                  className="rounded p-1 text-[#7C8091] hover:text-[#E6E8EE] transition-colors cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="p-2 flex items-center justify-center overflow-auto max-h-[calc(90vh-48px)]">
              <img src={zoomedImage} alt="Zoomed capture" className="max-w-full max-h-[80vh] object-contain rounded" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
