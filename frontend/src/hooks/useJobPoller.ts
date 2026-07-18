"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SearchJob } from "@/types";

export function useJobPoller(jobId: number | null, onNotFound?: () => void) {
  const [job, setJob] = useState<SearchJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onNotFoundRef = useRef(onNotFound);
  useEffect(() => { onNotFoundRef.current = onNotFound; }, [onNotFound]);

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await api.getJobStatus(jobId);
      setJob(data);
      setError(null);
      if (data.status === "pending" || data.status === "running" || data.status === "paused") {
        timerRef.current = setTimeout(poll, 2500);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Polling failed";
      // Job was deleted or backend restarted — clear silently
      if (msg.toLowerCase().includes("not found") || msg.includes("404")) {
        onNotFoundRef.current?.();
        return; // stop polling
      }
      setError(msg);
      // Retry on transient network errors, but slow down
      timerRef.current = setTimeout(poll, 5000);
    }
  }, [jobId]);

  useEffect(() => {
    setJob(null);
    setError(null);
    if (!jobId) return;
    poll();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [jobId, poll]);

  return { job, error };
}
