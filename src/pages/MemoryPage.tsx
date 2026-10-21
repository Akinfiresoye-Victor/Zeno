import React, { useState, useEffect } from 'react';
import { marked } from 'marked';
import {
  BrainCircuit,
  Save,
  RotateCcw,
  Sparkles,
  Eye,
  Edit3,
  Check,
  Copy,
  ExternalLink,
  Download,
} from 'lucide-react';
import { api } from '../services/api';

interface MemoryPageProps {
  apiKey?: string;
  activeModel?: string;
}

const EXTRACTION_PROMPT = `Export all of my stored memories and any context you've learned about me from past conversations. Preserve my words verbatim where possible, especially for instructions and preferences.

## Categories (output in this order):

1. **Instructions**: Rules I've explicitly asked you to follow going forward — tone, format, style, "always do X", "never do Y", and corrections to your behavior. Only include rules from stored memories, not from conversations.

2. **Identity**: Name, age, location, education, family, relationships, languages, and personal interests.

3. **Career**: Current and past roles, companies, and general skill areas.

4. **Projects**: Projects I meaningfully built or committed to. Ideally ONE entry per project. Include what it does, current status, and any key decisions. Use the project name or a short descriptor as the first words of the entry.

5. **Preferences**: Opinions, tastes, and working-style preferences that apply broadly.

## Format:

Use section headers for each category. Within each category, list one entry per line, sorted by oldest date first. Format each line as:

[YYYY-MM-DD] - Entry content here.

If no date is known, use [unknown] instead.

## Output:
- Wrap the entire export in a single code block for easy copying.
- After the code block, state whether this is the complete set or if more remain.`;

export const MemoryPage: React.FC<MemoryPageProps> = ({ apiKey, activeModel }) => {
  const [content, setContent] = useState('');
  const [notes, setNotes] = useState('');
  const [isPreview, setIsPreview] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [notice, setNotice] = useState('');
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  const fetchMemory = async () => {
    try {
      const mem = await api.memory.getMemory();
      setContent(mem || '');
    } catch (err) {
      console.error('Failed to load memory:', err);
    }
  };

  useEffect(() => {
    fetchMemory();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.memory.saveMemory(content);
      setNotice('Memory saved successfully!');
      setTimeout(() => setNotice(''), 3000);
    } catch (err: any) {
      setNotice(`Failed to save: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSynthesize = async () => {
    if (!notes.trim()) return;
    setIsSynthesizing(true);
    try {
      const merged = await api.memory.synthesize(notes, apiKey, activeModel);
      setContent(merged);
      setNotes('');
      setNotice('Memories synthesized and merged into Zeno profile!');
      setTimeout(() => setNotice(''), 3000);
    } catch (err: any) {
      setNotice(`Synthesis failed: ${err.message}`);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(EXTRACTION_PROMPT);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2500);
  };

  const handleReset = async () => {
    const defaultTemplate = `# User Profile & Persistent Memory\n\n## Personal Details\n- Assistant: Zeno Personal AI Assistant.\n\n## Preferences & Work Habits\n- Tone: Concise, technical, and direct.\n\n## Projects & Context\n- Active workspace: Local development.\n\n## Custom Instructions & Rules\n- When asked for hardware metrics, answer only what was asked.\n`;
    setContent(defaultTemplate);
    await api.memory.saveMemory(defaultTemplate);
    setNotice('Memory reset to clean template.');
    setTimeout(() => setNotice(''), 3000);
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0B0D13]">
      {/* Main Memory Editor Column */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-[#1F2637]">
        {/* Header */}
        <div className="p-4 border-b border-[#1F2637] bg-[#0E111A] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <BrainCircuit size={16} className="text-indigo-400" />
              <span>Persistent Memory</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Markdown profile automatically injected into Assistant and Agent contexts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPreview(!isPreview)}
              className="px-2.5 py-1.5 rounded-lg bg-[#151926] hover:bg-[#1C2233] border border-[#232B3E] text-slate-300 text-xs flex items-center gap-1.5 transition"
            >
              {isPreview ? <Edit3 size={13} /> : <Eye size={13} />}
              <span>{isPreview ? 'Edit Raw' : 'Preview'}</span>
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1.5 transition"
            >
              <Save size={13} />
              <span>Save Memory</span>
            </button>
          </div>
        </div>

        {notice && (
          <div className="px-4 py-2 bg-indigo-950/40 border-b border-indigo-500/20 text-xs text-indigo-300 flex items-center gap-2">
            <Check size={14} className="text-emerald-400" />
            <span>{notice}</span>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4">
          {isPreview ? (
            <div
              className="markdown-content p-4 rounded-xl bg-[#121520] border border-[#1F2637] select-text"
              dangerouslySetInnerHTML={{ __html: marked.parse(content || '') as string }}
            />
          ) : (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-full bg-[#10131E] border border-[#1F2637] rounded-xl p-4 text-xs font-mono text-slate-200 outline-none resize-none focus:border-indigo-500 transition leading-relaxed select-text"
              placeholder="# User Profile & Persistent Memory..."
            />
          )}
        </div>
      </div>

      {/* Synthesis & AI Memory Import Sidebar */}
      <div className="w-96 bg-[#0E111A] flex flex-col p-4 space-y-4 overflow-y-auto shrink-0 border-l border-[#1F2637]">
        {/* Personal AI Memory Extractor Card */}
        <div className="p-3.5 rounded-xl bg-[#121520] border border-indigo-500/30 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
              <Sparkles size={14} className="text-indigo-400" />
              <span>Import from Personal AI</span>
            </div>
            <button
              onClick={handleCopyPrompt}
              className="text-[11px] px-2 py-0.5 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 flex items-center gap-1 transition"
            >
              {copiedPrompt ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              <span>{copiedPrompt ? 'Copied!' : 'Copy Prompt'}</span>
            </button>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            Copy and paste this prompt into your personal AI (ChatGPT, Claude, or Gemini) to extract all your stored memories:
          </p>

          <pre className="p-2.5 rounded-lg bg-[#0A0C13] border border-[#1F2637] text-[10px] font-mono text-slate-400 overflow-x-auto max-h-36 whitespace-pre-wrap select-text leading-relaxed">
            {EXTRACTION_PROMPT}
          </pre>

          <div>
            <label className="text-[11px] text-slate-300 font-medium block mb-1">
              Paste AI Export Output:
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder="Paste the code block response from your personal AI here..."
              className="w-full p-2.5 text-xs bg-[#0F121B] border border-[#232B3E] rounded-lg text-slate-200 placeholder-slate-600 outline-none focus:border-indigo-500 font-mono"
            />
            <button
              onClick={handleSynthesize}
              disabled={isSynthesizing || !notes.trim()}
              className="w-full mt-2 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-medium flex items-center justify-center gap-1.5 transition shadow-xs"
            >
              <Sparkles size={13} className={isSynthesizing ? 'animate-spin' : ''} />
              <span>Synthesize & Merge into Zeno</span>
            </button>
          </div>
        </div>

        {/* Reset Memory */}
        <div className="pt-2 border-t border-[#1F2637]">
          <h3 className="text-xs font-semibold text-slate-300">Reset Memory</h3>
          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
            Restore the memory file back to the clean default template.
          </p>
          <button
            onClick={handleReset}
            className="mt-2 px-3 py-1.5 rounded-lg bg-red-600/15 hover:bg-red-600/25 text-red-300 border border-red-500/30 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <RotateCcw size={13} />
            <span>Reset to Default</span>
          </button>
        </div>
      </div>
    </div>
  );
};
