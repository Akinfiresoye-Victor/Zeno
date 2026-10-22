import React, { useState, useEffect, useRef, useCallback } from 'react';
import { marked } from 'marked';
import {
  Send,
  Plus,
  Trash2,
  Bot,
  Copy,
  Check,
  Sparkles,
  Paperclip,
  Activity,
  FileCode,
  CheckCircle2,
  Camera,
  RotateCcw,
  X,
  ChevronDown,
} from 'lucide-react';
import { AssistantThread, AssistantMessage, AttachedItem } from '../types';
import { api } from '../services/api';

interface AssistantPageProps {
  threads: AssistantThread[];
  activeThreadId: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => void;
  onDeleteThread: (threadId: string) => void;
  activeModel: string;
  apiKey: string;
  activeRunTitle?: string;
  isAgentRunning?: boolean;
}

const PASTE_LINE_THRESHOLD = 50;
const AUTO_COMPACT_MESSAGE_THRESHOLD = 30;

export const AssistantPage: React.FC<AssistantPageProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
  onDeleteThread,
  activeModel,
  apiKey,
  activeRunTitle,
  isAgentRunning = false,
}) => {
  const currentThread = threads.find((t) => t.id === activeThreadId) || threads[0];
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<AttachedItem[]>([]);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom of chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentThread?.messages, isSending]);

  // Close plus menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target as Node)) {
        setShowPlusMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-resize textarea
  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const maxH = 200; // max height in px
    ta.style.height = `${Math.min(ta.scrollHeight, maxH)}px`;
    ta.style.overflowY = ta.scrollHeight > maxH ? 'auto' : 'hidden';
  }, []);

  useEffect(() => {
    autoResize();
  }, [inputText, autoResize]);

  // Auto-compact: trigger compaction when thread reaches threshold
  useEffect(() => {
    if (!currentThread || !currentThread.messages) return;
    const msgCount = currentThread.messages.length;
    // Only compact when messages cross the threshold, and not already compacted recently
    if (msgCount >= AUTO_COMPACT_MESSAGE_THRESHOLD) {
      const alreadyCompacted = currentThread.messages.some(
        (m) => m.role === 'system' && m.content.startsWith('[Conversation Summary]')
      );
      if (!alreadyCompacted) {
        // Fire-and-forget auto compaction
        (async () => {
          try {
            if (window.pywebview?.api?.compact_conversation) {
              const result = await window.pywebview.api.compact_conversation({
                messages: currentThread.messages.slice(0, -10),
                model: activeModel,
                customApiKey: apiKey,
              });
              if (result && result.summary && !result.error) {
                const summaryMsg: AssistantMessage = {
                  id: `msg-compact-${Date.now()}`,
                  role: 'system',
                  content: `[Conversation Summary]\n${result.summary}`,
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                };
                // Replace old messages with summary + recent messages
                const recentMessages = currentThread.messages.slice(-10);
                currentThread.messages = [summaryMsg, ...recentMessages];
                await api.assistant.saveThreads(threads);
              }
            }
          } catch {
            // Silently fail auto-compaction
          }
        })();
      }
    }
  }, [currentThread?.messages?.length]);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text && attachments.length === 0) return;
    if (isSending || !currentThread) return;

    const userMsg: AssistantMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachments: [...attachments],
    };

    // Append to local state immediately
    const updatedMessages = [...(currentThread.messages || []), userMsg];
    currentThread.messages = updatedMessages;
    currentThread.updated_at = new Date().toISOString();
    setInputText('');
    setAttachments([]);
    setIsSending(true);

    try {
      const history = updatedMessages.slice(-10).map((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
      }));

      const res = await api.assistant.sendMessage({
        message: text,
        history,
        model: activeModel,
        customApiKey: apiKey,
        attachments: userMsg.attachments,
      });

      const assistantMsg: AssistantMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: res.reply || 'No response returned from model.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tokens: { input: res.inputTokens || 0, output: res.outputTokens || 0 },
      };

      currentThread.messages = [...updatedMessages, assistantMsg];
      await api.assistant.saveThreads(threads);
    } catch (err: any) {
      const errMsg: AssistantMessage = {
        id: `msg-err-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to communicate with AI model. Please verify API key.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      currentThread.messages = [...updatedMessages, errMsg];
      await api.assistant.saveThreads(threads);
    } finally {
      setIsSending(false);
    }
  };

  // Retry: resend the last user message to get a new response
  const handleRetry = async (failedMsgId: string) => {
    if (isSending || !currentThread) return;

    // Find the failed message and the user message before it
    const msgs = currentThread.messages || [];
    const failedIdx = msgs.findIndex((m) => m.id === failedMsgId);
    if (failedIdx === -1) return;

    // Remove the failed assistant message
    const withoutFailed = msgs.filter((m) => m.id !== failedMsgId);
    currentThread.messages = withoutFailed;

    // Find the last user message
    const lastUserMsg = [...withoutFailed].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;

    setIsSending(true);
    try {
      const history = withoutFailed.slice(-10).map((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
      }));

      const res = await api.assistant.sendMessage({
        message: lastUserMsg.content,
        history,
        model: activeModel,
        customApiKey: apiKey,
        attachments: lastUserMsg.attachments,
      });

      const assistantMsg: AssistantMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: res.reply || 'No response returned from model.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tokens: { input: res.inputTokens || 0, output: res.outputTokens || 0 },
      };
      currentThread.messages = [...withoutFailed, assistantMsg];
      await api.assistant.saveThreads(threads);
    } catch (err: any) {
      const errMsg: AssistantMessage = {
        id: `msg-err-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to communicate with AI model.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      currentThread.messages = [...withoutFailed, errMsg];
      await api.assistant.saveThreads(threads);
    } finally {
      setIsSending(false);
    }
  };

  // Agent Run Inspector Tool (Rule A)
  const handleInspectRun = async () => {
    if (!currentThread) return;
    const userMsg: AssistantMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: 'What is the agent currently working on?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const intermediateMessages = [...(currentThread.messages || []), userMsg];
    currentThread.messages = intermediateMessages;
    setIsSending(true);

    try {
      const inspectData = await api.assistant.inspectAgentRun('');
      const reply = inspectData.reply || 'No agent runs are currently active.';
      const toolMsg: AssistantMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `**[Agent Run Inspector]**\n\n${reply}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      currentThread.messages = [...intermediateMessages, toolMsg];
      await api.assistant.saveThreads(threads);
    } catch (err: any) {
      const errMsg: AssistantMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Failed to inspect agent run: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      currentThread.messages = [...intermediateMessages, errMsg];
    } finally {
      setIsSending(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    const reader = new FileReader();

    if (file.type.startsWith('image/')) {
      reader.onload = () => {
        setAttachments((prev) => [
          ...prev,
          {
            id: `att-${Date.now()}`,
            name: file.name,
            type: file.type,
            size: `${Math.round(file.size / 1024)} KB`,
            base64: reader.result as string,
          },
        ]);
      };
      reader.readAsDataURL(file);
    } else {
      reader.onload = () => {
        setAttachments((prev) => [
          ...prev,
          {
            id: `att-${Date.now()}`,
            name: file.name,
            type: file.type || 'text/plain',
            size: `${Math.round(file.size / 1024)} KB`,
            content: reader.result as string,
          },
        ]);
      };
      reader.readAsText(file);
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Screenshot capture
  const handleScreenshot = async () => {
    setShowPlusMenu(false);
    try {
      let screenshotData: any;
      if (window.pywebview?.api?.capture_screen) {
        screenshotData = await window.pywebview.api.capture_screen('all');
      } else {
        // Fallback: try fetch
        const res = await fetch('/api/screenshot').catch(() => null);
        if (res && res.ok) {
          screenshotData = await res.json();
        }
      }

      if (screenshotData && screenshotData.base64 && screenshotData.status !== 'failed') {
        setAttachments((prev) => [
          ...prev,
          {
            id: `att-ss-${Date.now()}`,
            name: screenshotData.name || `screenshot_${Date.now()}.png`,
            type: 'image/png',
            size: screenshotData.size || 'Screenshot',
            base64: screenshotData.base64,
          },
        ]);
      }
    } catch (err) {
      console.error('Screenshot capture failed:', err);
    }
  };

  // Paste content handler: large pastes (>50 lines) become attachments
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const pastedText = e.clipboardData.getData('text/plain');
    if (!pastedText) return;

    const lineCount = pastedText.split('\n').length;
    if (lineCount > PASTE_LINE_THRESHOLD) {
      e.preventDefault(); // Prevent default paste
      // Attach as "pasted text" file
      const sizeKb = Math.round(new Blob([pastedText]).size / 1024);
      setAttachments((prev) => [
        ...prev,
        {
          id: `att-paste-${Date.now()}`,
          name: `pasted_content_${lineCount}_lines.txt`,
          type: 'text/plain',
          size: `${sizeKb} KB`,
          content: pastedText,
        },
      ]);
    }
    // If <= threshold, let the default paste behavior work — text goes into the textarea
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0B0D13]">
      {/* Threads Sidebar */}
      <div className="w-56 border-r border-[#1F2637] bg-[#0E111A] flex flex-col shrink-0">
        <div className="p-3 border-b border-[#1F2637]">
          <button
            onClick={onCreateThread}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-indigo-600/15 hover:bg-indigo-600/25 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition"
          >
            <Plus size={14} />
            <span>New Chat</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {threads.map((t) => {
            const isSelected = t.id === currentThread?.id;
            return (
              <div
                key={t.id}
                onClick={() => onSelectThread(t.id)}
                className={`group flex items-center justify-between px-3 py-2 rounded-lg text-xs cursor-pointer transition ${
                  isSelected
                    ? 'bg-[#181D2B] text-slate-100 font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#141824]'
                }`}
              >
                <span className="truncate pr-1">{t.title}</span>
                {threads.length > 1 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteThread(t.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Context Bar / Agent Status Pill */}
        {isAgentRunning && (
          <div className="px-6 py-2 bg-indigo-950/30 border-b border-indigo-500/20 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-indigo-300">
              <Activity size={13} className="text-indigo-400 animate-pulse" />
              <span>Agent is running task: <strong>{activeRunTitle || 'Active Run'}</strong></span>
            </div>
            <button
              onClick={handleInspectRun}
              className="text-xs text-indigo-300 hover:text-indigo-200 underline font-medium flex items-center gap-1"
            >
              <span>Inspect Run</span>
            </button>
          </div>
        )}

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {currentThread?.messages.map((msg: AssistantMessage) => {
            const isUser = msg.role === 'user';
            const isSystem = msg.role === 'system';
            const isError = !isUser && msg.content.startsWith('Error:');

            if (isSystem) {
              return (
                <div key={msg.id} className="flex justify-center">
                  <div className="max-w-2xl px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-[11px] text-slate-400 italic text-center">
                    {msg.content}
                  </div>
                </div>
              );
            }

            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-xs font-mono font-medium ${
                    isUser
                      ? 'bg-slate-700 text-slate-200'
                      : 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  }`}
                >
                  {isUser ? 'U' : 'Z'}
                </div>

                {/* Content Bubble */}
                <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[85%]`}>
                  {/* Attachments */}
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {msg.attachments.map((att: AttachedItem) => (
                        <div
                          key={att.id}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#181D2B] border border-[#2B344B] text-[11px] text-slate-300"
                        >
                          <Paperclip size={11} className="text-slate-400" />
                          <span className="truncate max-w-[150px]">{att.name}</span>
                          <span className="text-[10px] text-slate-500">({att.size})</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div
                    className={`p-4 rounded-xl text-xs leading-relaxed ${
                      isUser
                        ? 'bg-indigo-600 text-white rounded-tr-none'
                        : isError
                        ? 'bg-red-950/30 border border-red-500/30 text-red-200 rounded-tl-none shadow-xs'
                        : 'bg-[#151926] border border-[#232B3E] text-slate-200 rounded-tl-none shadow-xs'
                    }`}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <div
                        className="markdown-content"
                        dangerouslySetInnerHTML={{
                          __html: marked.parse(msg.content) as string,
                        }}
                      />
                    )}
                  </div>

                  {/* Metadata & Actions */}
                  <div className="flex items-center gap-2 mt-1 px-1 text-[10px] text-slate-500">
                    <span>{msg.timestamp}</span>
                    {!isUser && (
                      <>
                        <button
                          onClick={() => handleCopy(msg.id, msg.content)}
                          className="hover:text-slate-300 transition flex items-center gap-1"
                        >
                          {copiedId === msg.id ? (
                            <Check size={11} className="text-emerald-400" />
                          ) : (
                            <Copy size={11} />
                          )}
                          <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                        </button>
                        {/* Retry button for error messages */}
                        {isError && (
                          <button
                            onClick={() => handleRetry(msg.id)}
                            disabled={isSending}
                            className="hover:text-indigo-300 transition flex items-center gap-1 text-slate-400 disabled:opacity-40"
                          >
                            <RotateCcw size={11} />
                            <span>Retry</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {isSending && (
            <div className="flex gap-3 max-w-2xl">
              <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-xs font-mono text-indigo-400 shrink-0">
                Z
              </div>
              <div className="px-4 py-3 rounded-xl rounded-tl-none bg-[#151926] border border-[#232B3E] text-xs text-slate-400 flex items-center gap-2">
                <Sparkles size={13} className="text-indigo-400 animate-spin" />
                <span>Thinking...</span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-[#1F2637] bg-[#0E111A]">
          {/* Quick Inspector Chip */}
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={handleInspectRun}
              className="text-[11px] px-2.5 py-1 rounded-full bg-[#181D2B] hover:bg-[#202738] text-slate-300 border border-[#2B344B] flex items-center gap-1.5 transition"
            >
              <Bot size={12} className="text-indigo-400" />
              <span>Inspect Active Agent Run</span>
            </button>
          </div>

          {/* Attached items preview */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2 p-2 rounded-lg bg-[#141824] border border-[#232B3E]">
              {attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#1C2233] text-xs text-slate-300 border border-[#2B344B]"
                >
                  {att.type.startsWith('image/') && att.base64 ? (
                    <img
                      src={att.base64}
                      alt={att.name}
                      className="w-8 h-8 rounded object-cover"
                    />
                  ) : (
                    <FileCode size={13} className="text-indigo-400" />
                  )}
                  <span className="truncate max-w-[150px]">{att.name}</span>
                  <span className="text-[10px] text-slate-500">({att.size})</span>
                  <button
                    onClick={() => setAttachments((prev) => prev.filter((a) => a.id !== att.id))}
                    className="text-slate-500 hover:text-red-400 ml-1"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2 bg-[#151926] border border-[#232B3E] rounded-xl p-2 focus-within:border-indigo-500 transition">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
            />

            {/* Plus button with dropdown menu */}
            <div className="relative" ref={plusMenuRef}>
              <button
                onClick={() => setShowPlusMenu(!showPlusMenu)}
                className={`p-2 rounded-lg transition ${
                  showPlusMenu
                    ? 'bg-indigo-600/20 text-indigo-300'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#1C2233]'
                }`}
                title="Attach file or take screenshot"
              >
                <Plus size={16} />
              </button>

              {/* Dropdown menu */}
              {showPlusMenu && (
                <div className="absolute bottom-full left-0 mb-2 w-44 py-1 rounded-xl bg-[#1A1F2E] border border-[#2B354C] shadow-2xl z-50 overflow-hidden">
                  <button
                    onClick={() => {
                      setShowPlusMenu(false);
                      fileInputRef.current?.click();
                    }}
                    className="w-full px-3 py-2 text-left text-xs text-slate-200 hover:bg-[#232B3E] flex items-center gap-2.5 transition"
                  >
                    <Paperclip size={14} className="text-slate-400" />
                    <span>Attach File</span>
                  </button>
                  <button
                    onClick={handleScreenshot}
                    className="w-full px-3 py-2 text-left text-xs text-slate-200 hover:bg-[#232B3E] flex items-center gap-2.5 transition"
                  >
                    <Camera size={14} className="text-indigo-400" />
                    <span>Screenshot</span>
                  </button>
                </div>
              )}
            </div>

            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onPaste={handlePaste}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask anything, discuss code, or inspect agent runs... (Enter to send)"
              rows={1}
              className="flex-1 bg-transparent text-xs text-slate-200 placeholder-slate-500 outline-none resize-none py-1.5 leading-relaxed"
              style={{ maxHeight: '200px', overflowY: 'hidden' }}
            />

            <button
              onClick={handleSend}
              disabled={isSending || (!inputText.trim() && attachments.length === 0)}
              className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white transition shrink-0"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
