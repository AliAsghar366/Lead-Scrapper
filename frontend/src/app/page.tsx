"use client";
import { useState, useEffect, useCallback } from "react";
import SearchBox from "@/components/SearchBox";
import JobStatus from "@/components/JobStatus";
import ResultsTable from "@/components/ResultsTable";
import HistorySidebar from "@/components/HistorySidebar";
import LeadListsPanel from "@/components/LeadListsPanel";
import { useJobPoller } from "@/hooks/useJobPoller";
import { api } from "@/lib/api";
import type { LeadList } from "@/types";

export default function HomePage() {
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [activeListId, setActiveListId] = useState<number | null>(null);
  const [lists, setLists] = useState<LeadList[]>([]);
  const [savedSearchQuery, setSavedSearchQuery] = useState<string>("");
  const { job, error } = useJobPoller(activeJobId);

  useEffect(() => {
    api.getLists().then(setLists).catch(() => {});
  }, []);

  async function refreshLists() {
    api.getLists().then(setLists).catch(() => {});
  }

  // When a new job starts, make it active but don't clear previous jobs —
  // they keep running in background, visible in the sidebar.
  function handleJobStarted(jobId: number, _query: string) {
    setActiveJobId(jobId);
    setActiveListId(null);
  }

  async function handleSaveSearch(query: string) {
    const name = prompt("Name this saved search:", query);
    if (!name) return;
    await api.createSavedSearch(name, query);
  }

  function handleRunSavedSearch(query: string) {
    setSavedSearchQuery(query);
  }

  const handlePause = useCallback(async () => {
    if (!activeJobId) return;
    try { await api.pauseJob(activeJobId); } catch { /* ignore */ }
  }, [activeJobId]);

  const handleResume = useCallback(async () => {
    if (!activeJobId) return;
    try { await api.resumeJob(activeJobId); } catch { /* ignore */ }
  }, [activeJobId]);

  const hasResults = (job?.result_count ?? 0) > 0;
  const isRunning = job?.status === "running" || job?.status === "pending" || job?.status === "paused";
  const showTable = activeJobId !== null || activeListId !== null;

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <div className="max-w-[1400px] mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight">Universal LeadCrawler AI</h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-tight">
              Discover · Enrich · Qualify — open web only, no paid APIs
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {/* Search */}
        <section className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-1">Find Any Business, Anywhere</h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-5">
            Enter a category and location — results stream in as they're discovered. Run multiple searches simultaneously.
          </p>
          <SearchBox
            onJobStarted={handleJobStarted}
            onSaveSearch={handleSaveSearch}
            initialQuery={savedSearchQuery}
            key={savedSearchQuery}
          />
        </section>

        {/* Three-column layout */}
        <div className="flex gap-6">
          {/* Left: history + lists + saved searches */}
          <div className="flex flex-col gap-6 flex-shrink-0">
            <HistorySidebar
              activeJobId={activeJobId}
              onSelect={(id) => { setActiveJobId(id); setActiveListId(null); }}
              onDeleted={(id) => { if (activeJobId === id) setActiveJobId(null); }}
              onClearedAll={() => setActiveJobId(null)}
            />
            <LeadListsPanel
              activeListId={activeListId}
              onSelectList={(id) => { setActiveListId(id); setActiveJobId(null); }}
              onRunSearch={handleRunSavedSearch}
            />
          </div>

          {/* Center: status + table */}
          <div className="flex-1 min-w-0 space-y-4">
            {activeJobId && (
              <JobStatus
                job={job}
                error={error}
                onPause={job?.status === "running" ? handlePause : undefined}
                onResume={job?.status === "paused" ? handleResume : undefined}
              />
            )}

            {activeListId && !activeJobId && (
              <div className="flex items-center gap-2 px-1">
                <div className="w-3 h-3 rounded-full"
                  style={{ background: lists.find(l => l.id === activeListId)?.color ?? "#3b82f6" }} />
                <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
                  {lists.find(l => l.id === activeListId)?.name ?? "List"}
                </span>
                <span className="text-xs text-zinc-400 ml-1">
                  {lists.find(l => l.id === activeListId)?.member_count ?? 0} leads
                </span>
              </div>
            )}

            {showTable ? (
              (activeJobId ? hasResults : true) ? (
                <ResultsTable
                  jobId={activeJobId}
                  liveRefresh={isRunning ?? false}
                  listId={activeListId}
                  lists={lists}
                />
              ) : (
                isRunning ? (
                  <div className="text-center py-8 text-zinc-400 text-sm">
                    Searching… results will appear here as they are found.
                  </div>
                ) : null
              )
            ) : (
              <div className="text-center py-16 text-zinc-400 dark:text-zinc-600">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <p className="text-sm">Search for leads above, or select a job/list on the left</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
