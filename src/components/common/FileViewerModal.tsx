import React, { useState, useEffect } from 'react';
import { marked } from 'marked';
import {
  X,
  FileCode,
  FolderOpen,
  Copy,
  Check,
  ExternalLink,
  AlertTriangle,
  Loader,
} from 'lucide-react';
import { api } from '../../services/api';

interface FileViewerModalProps {
  filePath: string;
  onClose: () => void;
}

export const FileViewerModal: React.FC<FileViewerModalProps> = ({ filePath, onClose }) => {
  const [fileData, setFileData] = useState<{
    ok?: boolean;
    name?: string;
    text?: string;
    base64?: string;
    mime_type?: string;
    is_directory?: boolean;
    is_unsupported?: boolean;
    message?: string;
    error?: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const loadContent = async () => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const res = await api.files.readFileBase64(filePath);
        if (isMounted) {
          if (res && (res.ok !== false)) {
            // Normalize: ensure we have at least name
            if (!res.name) {
              res.name = filePath.split(/[/\\]/).pop() || 'file';
            }
            setFileData(res);
          } else if (res && res.error) {
            setLoadError(res.error);
            setFileData({
              ok: false,
              name: filePath.split(/[/\\]/).pop() || 'file',
              error: res.error,
            });
          } else {
            setLoadError('Failed to read file preview — bridge returned empty result.');
            setFileData({
              ok: false,
              name: filePath.split(/[/\\]/).pop() || 'file',
              error: 'Failed to read file preview.',
            });
          }
        }
      } catch (err: any) {
        if (isMounted) {
          const msg = err?.message || 'Unknown error loading file.';
          setLoadError(msg);
          setFileData({
            ok: false,
            name: filePath.split(/[/\\]/).pop() || 'file',
            error: msg,
          });
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    loadContent();
    return () => {
      isMounted = false;
    };
  }, [filePath]);

  const handleCopy = () => {
    if (fileData?.text) {
      navigator.clipboard.writeText(fileData.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleReveal = async () => {
    try {
      await api.files.revealInExplorer(filePath);
    } catch {
      // Silently fail if bridge not available
    }
  };

  // Handle ESC key to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const fileName = fileData?.name || filePath.split(/[/\\]/).pop() || 'file';
  const isImage =
    fileData?.mime_type?.startsWith('image/') ||
    /\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)$/i.test(filePath);
  const isMarkdown = filePath.endsWith('.md');
  const isDirectory = fileData?.is_directory || false;
  const hasContent = !!(fileData?.text || (isImage && fileData?.base64));
  const isUnsupported = fileData?.is_unsupported || (!hasContent && !isLoading && !isDirectory);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-6 select-none"
      onClick={(e) => {
        // Close on backdrop click
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Loading State */}
      {isLoading && (
        <div className="w-full max-w-md bg-[#121520] border border-[#2B354C] rounded-2xl p-8 shadow-2xl flex flex-col items-center text-center">
          <Loader size={28} className="text-indigo-400 animate-spin mb-3" />
          <p className="text-xs text-slate-400">Loading file preview...</p>
          <p className="text-[10px] text-slate-600 font-mono mt-1 truncate max-w-sm">{filePath}</p>
        </div>
      )}

      {/* Error State */}
      {!isLoading && loadError && !isDirectory && (
        <div className="w-full max-w-md bg-[#121520] border border-[#2B354C] rounded-2xl p-6 shadow-2xl flex flex-col items-center text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 mb-4">
            <AlertTriangle size={28} />
          </div>
          <h3 className="text-base font-semibold text-slate-100">File Preview Error</h3>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">{loadError}</p>
          <div className="w-full mt-3 p-2 rounded-lg bg-[#0E111A] border border-[#1F2637] text-[11px] font-mono text-slate-300 truncate">
            {filePath}
          </div>
          <div className="flex items-center gap-3 mt-6 w-full">
            <button
              onClick={onClose}
              className="flex-1 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 bg-[#1A1F2E] hover:bg-[#22293C] rounded-lg transition"
            >
              Close
            </button>
            <button
              onClick={handleReveal}
              className="flex-1 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg flex items-center justify-center gap-1.5 transition shadow-xs"
            >
              <ExternalLink size={13} />
              <span>Reveal in Explorer</span>
            </button>
          </div>
        </div>
      )}

      {/* Directory or Unsupported File Type */}
      {!isLoading && !loadError && (isDirectory || isUnsupported) && (
        <div className="w-full max-w-md bg-[#121520] border border-[#2B354C] rounded-2xl p-6 shadow-2xl flex flex-col items-center text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-4">
            {isDirectory ? <FolderOpen size={28} /> : <AlertTriangle size={28} />}
          </div>

          <h3 className="text-base font-semibold text-slate-100">
            {isDirectory ? 'Folder Preview Not Supported' : 'File Type Not Supported'}
          </h3>

          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            {isDirectory
              ? 'Directories cannot be displayed inside the code previewer. You can explore the directory directly in your system file explorer.'
              : fileData?.message || 'This binary or system file type cannot be displayed as plain text.'}
          </p>

          <div className="w-full mt-3 p-2 rounded-lg bg-[#0E111A] border border-[#1F2637] text-[11px] font-mono text-slate-300 truncate">
            {filePath}
          </div>

          <div className="flex items-center gap-3 mt-6 w-full">
            <button
              onClick={onClose}
              className="flex-1 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 bg-[#1A1F2E] hover:bg-[#22293C] rounded-lg transition"
            >
              Close
            </button>
            <button
              onClick={handleReveal}
              className="flex-1 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg flex items-center justify-center gap-1.5 transition shadow-xs"
            >
              <ExternalLink size={13} />
              <span>Reveal in Explorer</span>
            </button>
          </div>
        </div>
      )}

      {/* Standard File Preview Modal */}
      {!isLoading && !loadError && hasContent && !isDirectory && !isUnsupported && (
        <div className="w-full max-w-4xl h-[85vh] bg-[#10131E] border border-[#2B354C] rounded-2xl flex flex-col shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-[#1F2637] bg-[#0E111A] flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-mono">
                <FileCode size={16} />
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-100 font-mono">{fileName}</div>
                <div className="text-[10px] text-slate-500 font-mono truncate max-w-xl">{filePath}</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {fileData?.text && (
                <button
                  onClick={handleCopy}
                  className="px-2.5 py-1 rounded bg-[#181D2B] hover:bg-[#22293B] text-slate-300 text-xs flex items-center gap-1 transition"
                >
                  {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy Content'}</span>
                </button>
              )}
              <button
                onClick={handleReveal}
                className="px-2.5 py-1 rounded bg-[#181D2B] hover:bg-[#22293B] text-slate-300 text-xs flex items-center gap-1 transition"
              >
                <ExternalLink size={12} />
                <span>Reveal in Explorer</span>
              </button>
              <button
                onClick={onClose}
                className="p-1 rounded text-slate-400 hover:text-slate-200 transition"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Content Viewer Body */}
          <div className="flex-1 overflow-y-auto p-4 bg-[#090B10]">
            {isImage && fileData?.base64 ? (
              <div className="flex items-center justify-center h-full p-4">
                <img
                  src={
                    fileData.base64.startsWith('data:')
                      ? fileData.base64
                      : `data:${fileData.mime_type || 'image/png'};base64,${fileData.base64}`
                  }
                  alt={fileName}
                  className="max-h-full max-w-full object-contain rounded-lg shadow-lg border border-[#2B354C]"
                />
              </div>
            ) : isMarkdown && fileData?.text ? (
              <div
                className="markdown-content p-4 max-w-3xl mx-auto select-text"
                dangerouslySetInnerHTML={{ __html: marked.parse(fileData.text) as string }}
              />
            ) : fileData?.text ? (
              <pre className="text-xs font-mono text-slate-200 p-4 whitespace-pre-wrap leading-relaxed select-text">
                {fileData.text}
              </pre>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-slate-500">
                No previewable text content found.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
