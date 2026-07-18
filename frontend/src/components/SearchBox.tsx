"use client";
import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
  onJobStarted: (jobId: number, query: string) => void;
  onSaveSearch?: (query: string) => void;
  initialQuery?: string;
}

const EXAMPLES_CITY = [
  "restaurants in Lahore",
  "hospitals in Karachi",
  "schools in Cambridge",
  "hotels in Dubai",
  "law firms in Toronto",
  "dentists in Chicago",
];

const EXAMPLES_STARTUP = [
  "startups in Germany",
  "startups in United Kingdom",
  "tech startups in Singapore",
  "fintech startups in United States",
  "saas companies in Canada",
  "ai startups in France",
];

export default function SearchBox({ onJobStarted, onSaveSearch, initialQuery }: Props) {
  const [query, setQuery] = useState(initialQuery ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [excludeExisting, setExcludeExisting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.submitSearch(query.trim(), excludeExisting);
      onJobStarted(res.job_id, query.trim());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start search");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. startups in Germany  or  restaurants in Lahore"
          className="flex-1 px-4 py-3 rounded-lg border border-zinc-300 dark:border-zinc-600
                     bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100
                     focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
        {onSaveSearch && query.trim() && (
          <button type="button" onClick={() => onSaveSearch(query.trim())}
            className="px-3 py-3 border border-zinc-300 dark:border-zinc-600 rounded-lg text-zinc-500 dark:text-zinc-400 hover:border-blue-400 hover:text-blue-600 transition-colors text-xs whitespace-nowrap">
            Save
          </button>
        )}
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                     text-white font-medium rounded-lg transition-colors text-sm"
        >
          {loading ? "Starting…" : "Search"}
        </button>
      </form>

      {/* Options row */}
      <div className="mt-2 flex items-center gap-2 px-1">
        <label className="flex items-center gap-1.5 cursor-pointer select-none text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300">
          <input
            type="checkbox"
            checked={excludeExisting}
            onChange={(e) => setExcludeExisting(e.target.checked)}
            className="w-3 h-3 rounded accent-blue-600"
          />
          Exclude leads already in database
        </label>
      </div>

      {error && (
        <p className="mt-2 text-sm text-red-500">{error}</p>
      )}

      <div className="mt-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0">By city/state:</span>
          {EXAMPLES_CITY.map((ex) => (
            <button
              key={ex}
              onClick={() => setQuery(ex)}
              className="px-3 py-1 text-xs bg-zinc-100 dark:bg-zinc-700 hover:bg-zinc-200
                         dark:hover:bg-zinc-600 rounded-full text-zinc-600 dark:text-zinc-300
                         transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0">Startups by country:</span>
          {EXAMPLES_STARTUP.map((ex) => (
            <button
              key={ex}
              onClick={() => setQuery(ex)}
              className="px-3 py-1 text-xs bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100
                         dark:hover:bg-blue-900/50 rounded-full text-blue-600 dark:text-blue-400
                         transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
