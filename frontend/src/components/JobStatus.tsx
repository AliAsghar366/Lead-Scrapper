"use client";
import type { SearchJob } from "@/types";

interface Props {
  job: SearchJob | null;
  error: string | null;
  onPause?: () => void;
  onResume?: () => void;
}

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  paused:  "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  done:    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  failed:  "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

export default function JobStatus({ job, error, onPause, onResume }: Props) {
  if (error) {
    return (
      <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
        <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
      </div>
    );
  }
  if (!job) return null;

  const isRunning = job.status === "running";
  const isPaused  = job.status === "paused";
  const isActive  = job.status === "pending" || isRunning || isPaused;

  return (
    <div className="p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {job.query}
          </p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            {job.entity_type && `${job.entity_type}`}
            {job.location && ` in ${job.location}`}
            {" · "}Job #{job.job_id}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isRunning && onPause && (
            <button
              onClick={onPause}
              className="px-3 py-1 text-xs rounded-md border border-orange-300 text-orange-700 hover:bg-orange-50 dark:border-orange-600 dark:text-orange-400 dark:hover:bg-orange-900/20 transition-colors font-medium"
            >
              ⏸ Pause
            </button>
          )}
          {isPaused && onResume && (
            <button
              onClick={onResume}
              className="px-3 py-1 text-xs rounded-md border border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-600 dark:text-blue-400 dark:hover:bg-blue-900/20 transition-colors font-medium"
            >
              ▶ Resume
            </button>
          )}
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLE[job.status] ?? ""}`}>
            {job.status}
          </span>
        </div>
      </div>

      {isActive && (
        <div className="mt-3 w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full ${isPaused ? "bg-orange-400" : "bg-blue-500 animate-pulse"}`}
            style={{ width: "60%" }}
          />
        </div>
      )}

      {isPaused && (
        <p className="mt-2 text-xs text-orange-600 dark:text-orange-400">
          Paused — {job.result_count} leads found so far. Click Resume to continue.
        </p>
      )}

      {job.status === "done" && (
        <p className="mt-2 text-sm text-green-700 dark:text-green-400">
          Found <span className="font-semibold">{job.result_count}</span> leads
        </p>
      )}

      {job.status === "failed" && job.error_message && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400">{job.error_message}</p>
      )}
    </div>
  );
}
