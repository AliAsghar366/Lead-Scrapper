"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SearchJob } from "@/types";

export function useJobPoller(jobId: number | null) {
  const [job, setJob] = useState<SearchJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await api.getJobStatus(jobId);
      setJob(data);
      if (data.status === "pending" || data.status === "running" || data.status === "paused") {
        timerRef.current = setTimeout(poll, 2500);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Polling failed");
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    poll();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [jobId, poll]);

  return { job, error };
}
