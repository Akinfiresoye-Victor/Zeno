import React, { useState, useEffect } from 'react';
import {
  FolderOpen,
  FileCode,
  FileText,
  Image as ImageIcon,
  ExternalLink,
  Search,
  Eye,
  RefreshCw,
  Copy,
  Check,
  Trash2,
  Layers,
  Bot,
  AlertCircle,
} from 'lucide-react';
import { WorkspaceFile, AgentRunRecord, ChecklistStep } from '../types';
import { api } from '../services/api';

interface FilesPageProps {
  projectFolder: string;
  projectName: string;
  onOpenFileViewer: (path: string) => void;
}

interface TaskFileGroup {
  run: AgentRunRecord;
  files: string[];
}

export const FilesPage: React.FC<FilesPageProps> = ({
  projectFolder,
  projectName,
  onOpenFileViewer,
}) => {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [filterQuery, setFilterQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'all' | 'tasks'>('all');
  const [taskGroups, setTaskGroups] = useState<TaskFileGroup[]>([]);
  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; all: boolean } | null>(null);

  const fetchFiles = async () => {
    setIsLoading(true);
    try {
      const [result, runs] = await Promise.all([
        api.files.listFiles(projectFolder),
        api.agent.getRuns(),
      ]);
      setFiles(result || []);
      setSelectedPaths(new Set());

      // Build task groups by inspecting checklist steps of each run
      const groups: TaskFileGroup[] = [];
      for (const r of runs) {
        try {
          const cl = await api.agent.getRunChecklist(r.project_folder);
          const runFiles = new Set<string>();
          (cl.steps || []).forEach((step: ChecklistStep) => {
            (step.evidence?.files_created || []).forEach((f: string) => runFiles.add(f));
          });
          groups.push({
            run: r,
            files: Array.from(runFiles),
          });
        } catch {
          groups.push({ run: r, files: [] });
        }
      }
      setTaskGroups(groups);
    } catch (err) {
      console.error('Failed to list workspace files:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [projectFolder]);

  const handleReveal = async (filePath: string) => {
    await api.files.revealInExplorer(filePath);
  };

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path);
    setCopiedPath(path);
    setTimeout(() => setCopiedPath(null), 2000);
  };

  const toggleSelect = (path: string) => {
    const updated = new Set(selectedPaths);
    if (updated.has(path)) {
      updated.delete(path);
    } else {
      updated.add(path);
    }
    setSelectedPaths(updated);
  };

  const toggleSelectAll = () => {
    if (selectedPaths.size === filtered.length && filtered.length > 0) {
      setSelectedPaths(new Set());
    } else {
      setSelectedPaths(new Set(filtered.map((f) => f.path)));
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    try {
      if (deleteConfirm.all) {
        await api.delete.files({ all: true, projectFolder });
      } else {
        await api.delete.files({ paths: Array.from(selectedPaths), projectFolder });
      }
      await fetchFiles();
    } catch (err) {
      console.error('Failed to delete files:', err);
    } finally {
      setDeleteConfirm(null);
    }
  };

  const filtered = files.filter(
    (f) =>
      f.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
      f.path.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const getFileIcon = (mime: string, name: string) => {
    if (mime?.startsWith('image/')) return <ImageIcon size={16} className="text-pink-400" />;
    if (name.endsWith('.py') || name.endsWith('.ts') || name.endsWith('.js') || name.endsWith('.json')) {
      return <FileCode size={16} className="text-indigo-400" />;
    }
    return <FileText size={16} className="text-slate-400" />;
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#0B0D13]">
      {/* Top Header & Search Bar */}
      <div className="p-4 border-b border-[#1F2637] bg-[#0E111A] flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <FolderOpen size={16} className="text-indigo-400" />
              <span>Workspace Files</span>
            </h2>
            {projectName && (
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                {projectName}
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5 truncate max-w-xl">
            {projectFolder || 'No project directory selected'}
          </p>
        </div>

        {/* View Mode & Actions Toolbar */}
        <div className="flex items-center gap-2">
          {/* Mode Switcher */}
          <div className="flex bg-[#121520] border border-[#232B3E] rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setViewMode('all')}
              className={`px-2.5 py-1 rounded-md font-medium transition ${
                viewMode === 'all'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Files
            </button>
            <button
              onClick={() => setViewMode('tasks')}
              className={`px-2.5 py-1 rounded-md font-medium flex items-center gap-1 transition ${
                viewMode === 'tasks'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Bot size={13} />
              <span>By Agent Task</span>
            </button>
          </div>

          {/* Search Filter */}
          <div className="flex items-center gap-2 bg-[#151926] border border-[#232B3E] px-2.5 py-1.5 rounded-lg">
            <Search size={13} className="text-slate-400" />
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter files..."
              className="bg-transparent text-xs text-slate-200 outline-none w-36 placeholder-slate-500"
            />
          </div>

          {/* Delete Buttons */}
          {selectedPaths.size > 0 && (
            <button
              onClick={() => setDeleteConfirm({ open: true, all: false })}
              className="px-2.5 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-medium flex items-center gap-1.5 transition"
            >
              <Trash2 size={13} />
              <span>Delete Selected ({selectedPaths.size})</span>
            </button>
          )}

          {files.length > 0 && (
            <button
              onClick={() => setDeleteConfirm({ open: true, all: true })}
              className="px-2.5 py-1.5 rounded-lg bg-[#181D2B] hover:bg-red-950/30 text-slate-400 hover:text-red-300 border border-[#2B354C] hover:border-red-500/30 text-xs font-medium flex items-center gap-1 transition"
              title="Delete all workspace files"
            >
              <Trash2 size={13} />
              <span>Delete All</span>
            </button>
          )}

          <button
            onClick={fetchFiles}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-[#151926] hover:bg-[#1C2233] border border-[#232B3E] text-slate-400 hover:text-slate-200 transition"
            title="Refresh Files"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Main Files Area */}
      <div className="flex-1 overflow-y-auto p-4">
        {viewMode === 'tasks' ? (
          /* Organized By Agent Task View */
          <div className="space-y-4">
            {taskGroups.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                <Bot size={36} className="text-slate-600 mb-2" />
                <p className="text-xs font-medium text-slate-400">No agent runs recorded</p>
                <p className="text-[11px] text-slate-500 mt-1">
                  When you run tasks in Agent Workspace, files created by each step will appear here.
                </p>
              </div>
            ) : (
              taskGroups.map((group) => (
                <div
                  key={group.run.id}
                  className="p-4 rounded-xl bg-[#121520] border border-[#1F2637] space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
                        <Bot size={13} />
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-slate-200 font-mono">
                          {group.run.title}
                        </span>
                        <span className="text-[11px] text-slate-500 ml-2">
                          "{group.run.task_prompt}"
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 uppercase">
                      {group.run.status}
                    </span>
                  </div>

                  {group.files.length === 0 ? (
                    <div className="text-[11px] text-slate-500 italic pl-8">
                      No files generated by this agent run.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 pl-8">
                      {group.files.map((file) => (
                        <div
                          key={file}
                          className="flex items-center justify-between p-2.5 rounded-lg bg-[#0E111A] border border-[#1F2637] hover:border-slate-600 transition"
                        >
                          <div className="flex items-center gap-2 truncate pr-2">
                            <FileCode size={14} className="text-indigo-400 shrink-0" />
                            <span className="text-xs font-mono text-slate-200 truncate">{file}</span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => onOpenFileViewer(file)}
                              className="p-1 text-slate-400 hover:text-indigo-300 transition"
                              title="View In-App"
                            >
                              <Eye size={13} />
                            </button>
                            <button
                              onClick={() => handleReveal(file)}
                              className="p-1 text-slate-400 hover:text-slate-200 transition"
                              title="Reveal in Explorer"
                            >
                              <ExternalLink size={13} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          /* All Files Table View */
          filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center text-slate-500">
              <FolderOpen size={36} className="text-slate-600 mb-2" />
              <p className="text-xs font-medium text-slate-400">No files found in workspace</p>
              <p className="text-[11px] text-slate-500 max-w-sm mt-1">
                The agent has not generated files in this project directory yet.
              </p>
            </div>
          ) : (
            <div className="bg-[#121520] border border-[#1F2637] rounded-xl overflow-hidden shadow-xs">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#1F2637] bg-[#0F121B] text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
                    <th className="py-2.5 px-3 w-8">
                      <input
                        type="checkbox"
                        checked={selectedPaths.size === filtered.length && filtered.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded cursor-pointer accent-indigo-600"
                      />
                    </th>
                    <th className="py-2.5 px-4">Name</th>
                    <th className="py-2.5 px-4">Size</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#181D2B]">
                  {filtered.map((file) => {
                    const isSelected = selectedPaths.has(file.path);
                    return (
                      <tr
                        key={file.path}
                        className={`hover:bg-[#161B29] transition group ${
                          isSelected ? 'bg-indigo-950/20' : ''
                        }`}
                      >
                        <td className="py-2.5 px-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(file.path)}
                            className="rounded cursor-pointer accent-indigo-600"
                          />
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2.5">
                            {getFileIcon(file.mime_type, file.name)}
                            <div>
                              <div className="font-mono text-slate-200 font-medium">{file.name}</div>
                              <div className="text-[10px] font-mono text-slate-500 truncate max-w-md">
                                {file.path}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="py-2.5 px-4 font-mono text-slate-400">{file.size}</td>
                        <td className="py-2.5 px-4 font-mono text-slate-500">{file.mime_type}</td>
                        <td className="py-2.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5 opacity-90 group-hover:opacity-100">
                            <button
                              onClick={() => onOpenFileViewer(file.path)}
                              className="px-2 py-1 rounded bg-[#1A2030] hover:bg-indigo-600/20 text-slate-300 hover:text-indigo-300 border border-[#2B354C] flex items-center gap-1 text-[11px] transition"
                              title="Open In-App Preview"
                            >
                              <Eye size={12} />
                              <span>View</span>
                            </button>
                            <button
                              onClick={() => handleReveal(file.path)}
                              className="px-2 py-1 rounded bg-[#1A2030] hover:bg-[#232B40] text-slate-400 hover:text-slate-200 border border-[#2B354C] flex items-center gap-1 text-[11px] transition"
                              title="Reveal in Explorer"
                            >
                              <ExternalLink size={12} />
                              <span>Reveal</span>
                            </button>
                            <button
                              onClick={() => handleCopyPath(file.path)}
                              className="p-1 rounded bg-[#1A2030] hover:bg-[#232B40] text-slate-400 hover:text-slate-200 border border-[#2B354C] transition"
                              title="Copy File Path"
                            >
                              {copiedPath === file.path ? (
                                <Check size={12} className="text-emerald-400" />
                              ) : (
                                <Copy size={12} />
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm bg-[#121520] border border-[#2B354C] rounded-2xl p-5 shadow-2xl flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 mb-3">
              <AlertCircle size={24} />
            </div>
            <h3 className="text-sm font-semibold text-slate-100">
              {deleteConfirm.all ? 'Delete All Files?' : `Delete ${selectedPaths.size} Selected Files?`}
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              This action cannot be undone. Selected files will be permanently deleted from the workspace.
            </p>
            <div className="flex items-center gap-2 mt-5 w-full">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 bg-[#1A1F2E] rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="flex-1 py-2 text-xs font-medium text-white bg-red-600 hover:bg-red-500 rounded-lg transition"
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
