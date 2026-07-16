"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { SearchJob } from "@/types";

interface Props {
  activeJobId: number | null;
  onSelect: (jobId: number) => void;
  onDeleted?: (jobId: number) => void;
  onClearedAll?: () => void;
}

const DOT: Record<string, string> = {
  pending: "bg-yellow-400",
  running: "bg-blue-500 animate-pulse",
  paused:  "bg-orange-400",
  done:    "bg-green-500",
  failed:  "bg-red-500",
};

export default function HistorySidebar({ activeJobId, onSelect, onDeleted, onClearedAll }: Props) {
  const [jobs, setJobs]               = useState<SearchJob[]>([]);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [clearing, setClearing]       = useState(false);

  const load = useCallback(() => {
    api.getHistory().then(setJobs).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [load]);

  async function handlePause(e: React.MouseEvent, jobId: number) {
    e.stopPropagation();
    setActionLoading(jobId);
    try { await api.pauseJob(jobId); } catch { /* refresh anyway */ }
    load();
    setActionLoading(null);
  }

  async function handleResume(e: React.MouseEvent, jobId: number) {
    e.stopPropagation();
    setActionLoading(jobId);
    try { await api.resumeJob(jobId); } catch { /* refresh anyway */ }
    load();
    setActionLoading(null);
  }

  async function handleDelete(e: React.MouseEvent, jobId: number) {
    e.stopPropagation();
    setActionLoading(jobId);
    try {
      await api.deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
      onDeleted?.(jobId);
    } catch {
      load();
    } finally {
      setActionLoading(null);
    }
  }

  async function handleClearAll() {
    if (!confirm("Delete ALL jobs and leads? This cannot be undone.")) return;
    setClearing(true);
    try {
      await api.deleteAllJobs();
      setJobs([]);
      onClearedAll?.();
    } catch {
      load();
    } finally {
      setClearing(false);
    }
  }

  if (jobs.length === 0) return null;

  return (
    <aside className="w-64 shrink-0 hidden lg:block">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
          Recent Searches
        </h3>
        <button
          onClick={handleClearAll}
          disabled={clearing}
          title="Clear all jobs and leads"
          className="text-xs text-red-400 hover:text-red-600 dark:hover:text-red-300 disabled:opacity-40 transition-colors"
        >
          {clearing ? "…" : "Clear all"}
        </button>
      </div>
      <ul className="space-y-1">
        {jobs.map((job) => {
          const canDelete = job.status !== "running" && job.status !== "paused";
          const loading   = actionLoading === job.job_id;
          return (
            <li key={job.job_id}>
              <button
                onClick={() => onSelect(job.job_id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeJobId === job.job_id
                    ? "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                    : "hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT[job.status] ?? "bg-zinc-400"}`} />
                  <span className="truncate text-xs flex-1">{job.query}</span>

                  {/* Pause for running jobs */}
                  {job.status === "running" && (
                    <span
                      role="button"
                      onClick={(e) => handlePause(e, job.job_id)}
                      title="Pause"
                      className={`text-xs px-1.5 py-0.5 rounded border border-orange-300 text-orange-600 hover:bg-orange-50 dark:border-orange-700 dark:text-orange-400 transition-colors flex-shrink-0 ${loading ? "opacity-50 pointer-events-none" : ""}`}
                    >
                      ⏸
                    </span>
                  )}

                  {/* Resume for paused jobs */}
                  {job.status === "paused" && (
                    <span
                      role="button"
                      onClick={(e) => handleResume(e, job.job_id)}
                      title="Resume"
                      className={`text-xs px-1.5 py-0.5 rounded border border-blue-300 text-blue-600 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-400 transition-colors flex-shrink-0 ${loading ? "opacity-50 pointer-events-none" : ""}`}
                    >
                      ▶
                    </span>
                  )}

                  {/* Delete for done/failed/pending jobs */}
                  {canDelete && (
                    <span
                      role="button"
                      onClick={(e) => handleDelete(e, job.job_id)}
                      title="Delete this job"
                      className={`text-xs text-zinc-400 hover:text-red-500 transition-colors flex-shrink-0 ${loading ? "opacity-50 pointer-events-none" : ""}`}
                    >
                      ✕
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-400 mt-0.5 pl-3.5">
                  {job.result_count} leads
                  {job.status === "paused" && <span className="ml-1 text-orange-400">· paused</span>}
                </p>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
