"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { LeadFilters } from "@/lib/api";
import { safeUrl } from "@/lib/utils";
import type { Lead, LeadListResponse, LeadStatus, LeadList } from "@/types";
import LeadDetailPanel from "./LeadDetailPanel";

interface Props {
  jobId: number | null;
  liveRefresh: boolean;
  listId?: number | null;
  lists: LeadList[];
}

type SortField = "created_at" | "score" | "name";

const STATUS_OPTIONS: { value: LeadStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "rejected", label: "Rejected" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

const STATUS_COLORS: Record<string, string> = {
  new: "bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300",
  contacted: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  qualified: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  won: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  lost: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
};

const QUICK_FILTERS: { key: keyof LeadFilters; label: string }[] = [
  { key: "has_phone",   label: "Phone" },
  { key: "has_email",   label: "Email" },
  { key: "has_website", label: "Website" },
  { key: "has_address", label: "Address" },
  { key: "has_social",  label: "Social" },
];

function ScoreDot({ score }: { score: number }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-400" : "bg-zinc-300 dark:bg-zinc-600";
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs text-zinc-500">{score}</span>
    </span>
  );
}

function ExternalLink({ href, label }: { href?: string | null; label: string }) {
  if (!href) return <span className="text-zinc-400 text-xs">—</span>;
  return (
    <a href={safeUrl(href) ?? "#"} target="_blank" rel="noopener noreferrer"
      className="text-blue-600 dark:text-blue-400 hover:underline text-xs truncate max-w-[110px] block" title={href}>
      {label}
    </a>
  );
}

export default function ResultsTable({ jobId, liveRefresh, listId, lists }: Props) {
  const [data, setData] = useState<LeadListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<LeadFilters>({});
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [detailLead, setDetailLead] = useState<Lead | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [bulkAction, setBulkAction] = useState("");
  const [allTagsList, setAllTagsList] = useState<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeFilterCount = Object.values(filters).filter(v => v !== undefined && v !== "" && v !== false).length;

  useEffect(() => {
    api.getAllTags().then(setAllTagsList).catch(() => {});
  }, []);

  function buildFilters(): LeadFilters {
    return { ...filters, list_id: listId ?? undefined, sort_by: sortBy, sort_dir: sortDir };
  }

  async function fetchPage(p: number) {
    setLoading(true);
    try {
      const f = buildFilters();
      let result: LeadListResponse;
      if (jobId) {
        result = await api.getResults(jobId, p, 50, f);
      } else {
        result = await api.getLeads(p, 50, f);
      }
      setData(result);
    } finally { setLoading(false); }
  }

  function schedulePoll(p: number) {
    timerRef.current = setTimeout(async () => {
      try {
        const f = buildFilters();
        const result = jobId
          ? await api.getResults(jobId, p, 50, f)
          : await api.getLeads(p, 50, f);
        setData(result);
      } catch { /* ignore */ }
      if (liveRefresh) schedulePoll(p);
    }, 3000);
  }

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setSelected(new Set());
    fetchPage(page).then(() => { if (liveRefresh) schedulePoll(page); });
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, page, filters, sortBy, sortDir, listId]);

  useEffect(() => {
    if (!liveRefresh) {
      if (timerRef.current) clearTimeout(timerRef.current);
      fetchPage(page);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveRefresh]);

  function toggleSelect(id: number) {
    setSelected(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }

  function toggleAll() {
    if (!data) return;
    const allIds = data.items.map(i => i.id);
    setSelected(prev => prev.size === allIds.length ? new Set() : new Set(allIds));
  }

  async function executeBulk() {
    if (!bulkAction || selected.size === 0) return;
    const ids = Array.from(selected);
    if (bulkAction.startsWith("status:")) {
      await api.bulkAction(ids, "set_status", bulkAction.replace("status:", ""));
    } else if (bulkAction === "delete") {
      if (!confirm(`Delete ${ids.length} leads?`)) return;
      await api.bulkAction(ids, "delete");
    }
    setSelected(new Set());
    setBulkAction("");
    await fetchPage(page);
  }

  function handleLeadUpdated(updated: Lead) {
    setData(prev => {
      if (!prev) return prev;
      return { ...prev, items: prev.items.map(i => i.id === updated.id ? updated : i) };
    });
    setDetailLead(updated);
  }

  const f = filters;
  const anyFilter = activeFilterCount > 0;

  if (loading && !data) {
    return <div className="animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-800 h-48 w-full" />;
  }

  return (
    <>
      <div className="space-y-3">
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Quick field filters */}
          <div className="flex flex-wrap items-center gap-1.5">
            {QUICK_FILTERS.map(({ key, label }) => {
              const active = !!f[key];
              return (
                <button key={key} onClick={() => { setFilters(p => ({ ...p, [key]: !p[key] || undefined })); setPage(1); }}
                  className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                    active ? "bg-blue-600 border-blue-600 text-white" : "border-zinc-300 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400 hover:border-blue-400 hover:text-blue-600"
                  }`}>
                  {active ? "✓ " : ""}{label}
                </button>
              );
            })}
          </div>

          {/* Status filter */}
          <select
            value={f.status ?? ""}
            onChange={e => { setFilters(p => ({ ...p, status: e.target.value as LeadStatus | "" })); setPage(1); }}
            className="text-xs px-2.5 py-1 rounded-full border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          {/* Advanced toggle */}
          <button onClick={() => setShowAdvanced(!showAdvanced)}
            className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
              showAdvanced ? "bg-zinc-800 border-zinc-800 text-white dark:bg-zinc-100 dark:text-zinc-900" : "border-zinc-300 dark:border-zinc-600 text-zinc-500 hover:border-zinc-500"
            }`}>
            Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
          </button>

          {anyFilter && (
            <button onClick={() => { setFilters({}); setPage(1); }}
              className="text-xs text-zinc-400 hover:text-red-500 transition-colors">
              Clear all
            </button>
          )}

          <div className="ml-auto flex items-center gap-3">
            {liveRefresh && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                Live
              </span>
            )}
            {/* Sort */}
            <select value={`${sortBy}:${sortDir}`}
              onChange={e => { const [b, d] = e.target.value.split(":"); setSortBy(b as SortField); setSortDir(d as "asc"|"desc"); setPage(1); }}
              className="text-xs px-2 py-1 rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              <option value="created_at:desc">Newest first</option>
              <option value="created_at:asc">Oldest first</option>
              <option value="score:desc">Highest score</option>
              <option value="score:asc">Lowest score</option>
              <option value="name:asc">Name A–Z</option>
            </select>
            <p className="text-xs text-zinc-500">
              <span className="font-semibold text-zinc-800 dark:text-zinc-100">{data?.total ?? 0}</span> leads
              {anyFilter && <span className="ml-1 text-blue-600">(filtered)</span>}
            </p>
            {jobId && (
              <>
                <a href={api.exportExcelUrl(jobId, buildFilters())}
                  className="px-3 py-1.5 text-xs bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors">
                  Excel
                </a>
                <a href={api.exportCsvUrl(jobId, buildFilters())}
                  className="px-3 py-1.5 text-xs bg-zinc-600 hover:bg-zinc-700 text-white rounded-md transition-colors">
                  CSV
                </a>
              </>
            )}
          </div>
        </div>

        {/* Advanced filter panel */}
        {showAdvanced && (
          <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg p-3 flex flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-zinc-500">Min score</label>
              <input type="number" min={0} max={100} value={f.min_score ?? ""}
                onChange={e => { setFilters(p => ({ ...p, min_score: e.target.value ? +e.target.value : undefined })); setPage(1); }}
                className="w-20 text-xs px-2 py-1.5 rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-800 dark:text-zinc-100" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-zinc-500">Tag</label>
              <select value={f.tags ?? ""}
                onChange={e => { setFilters(p => ({ ...p, tags: e.target.value || undefined })); setPage(1); }}
                className="text-xs px-2 py-1.5 rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-800 dark:text-zinc-100">
                <option value="">Any tag</option>
                {allTagsList.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-[160px]">
              <label className="text-xs text-zinc-500">Search name / email / website</label>
              <input type="text" value={f.search ?? ""}
                onChange={e => { setFilters(p => ({ ...p, search: e.target.value || undefined })); setPage(1); }}
                placeholder="keyword…"
                className="text-xs px-2 py-1.5 rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-800 dark:text-zinc-100" />
            </div>
          </div>
        )}

        {/* Bulk action bar */}
        {selected.size > 0 && (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-blue-600 text-white rounded-lg">
            <span className="text-sm font-medium">{selected.size} selected</span>
            <select value={bulkAction} onChange={e => setBulkAction(e.target.value)}
              className="text-xs px-2 py-1 rounded bg-blue-700 text-white border border-blue-500">
              <option value="">Choose action…</option>
              <optgroup label="Set status">
                {["contacted","qualified","rejected","won","lost"].map(s => (
                  <option key={s} value={`status:${s}`}>Mark as {s}</option>
                ))}
              </optgroup>
              <option value="delete">Delete selected</option>
            </select>
            <button onClick={executeBulk} disabled={!bulkAction}
              className="px-3 py-1 text-xs bg-white text-blue-700 font-medium rounded hover:bg-blue-50 disabled:opacity-50 transition-colors">
              Apply
            </button>
            <button onClick={() => setSelected(new Set())} className="ml-auto text-blue-200 hover:text-white text-xs">
              Cancel
            </button>
          </div>
        )}

        {(!data || data.items.length === 0) ? (
          <div className="text-center py-8 text-zinc-400 text-sm">
            {liveRefresh ? "Searching… results will appear here as they are found." : "No results found."}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                <tr>
                  <th className="w-8 px-3 py-2.5">
                    <input type="checkbox" checked={selected.size === data.items.length && data.items.length > 0}
                      onChange={toggleAll} className="rounded" />
                  </th>
                  {["Name", "Score", "Status", "Website", "Email", "Phone", "Address", "FB", "IG", "LI"].map(h => (
                    <th key={h} className="px-3 py-2.5 text-left text-xs font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {data.items.map(lead => (
                  <tr key={lead.id}
                    className={`transition-colors cursor-pointer ${
                      selected.has(lead.id)
                        ? "bg-blue-50 dark:bg-blue-950"
                        : "hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    }`}
                    onClick={() => setDetailLead(lead)}>
                    <td className="px-3 py-2.5" onClick={e => { e.stopPropagation(); toggleSelect(lead.id); }}>
                      <input type="checkbox" checked={selected.has(lead.id)} onChange={() => {}} className="rounded" />
                    </td>
                    <td className="px-3 py-2.5 font-medium max-w-[160px] truncate text-xs text-zinc-900 dark:text-zinc-100">
                      {lead.name || <span className="text-zinc-400">—</span>}
                      {lead.email_verified === true && <span className="ml-1 text-emerald-500 text-xs" title="Email verified">✓</span>}
                    </td>
                    <td className="px-3 py-2.5"><ScoreDot score={lead.score} /></td>
                    <td className="px-3 py-2.5">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[lead.status] ?? STATUS_COLORS.new}`}>
                        {lead.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <ExternalLink href={lead.website}
                        label={lead.website ? (() => { try { return new URL(safeUrl(lead.website)!).hostname; } catch { return lead.website ?? "—"; } })() : "—"} />
                    </td>
                    <td className="px-3 py-2.5 text-xs text-zinc-700 dark:text-zinc-300 whitespace-nowrap">
                      {lead.email ? <a href={`mailto:${lead.email}`} className="text-blue-600 dark:text-blue-400 hover:underline" onClick={e => e.stopPropagation()}>{lead.email}</a>
                        : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-zinc-700 dark:text-zinc-300 whitespace-nowrap">
                      {lead.phone || <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-zinc-600 dark:text-zinc-400 max-w-[160px] truncate">
                      {lead.address || <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-2.5"><ExternalLink href={lead.facebook} label="FB" /></td>
                    <td className="px-3 py-2.5"><ExternalLink href={lead.instagram} label="IG" /></td>
                    <td className="px-3 py-2.5"><ExternalLink href={lead.linkedin} label="LI" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex justify-center gap-2 pt-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 disabled:opacity-40 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors">
              Prev
            </button>
            <span className="px-3 py-1 text-xs text-zinc-600 dark:text-zinc-400">{page} / {data.total_pages}</span>
            <button onClick={() => setPage(p => Math.min(data.total_pages, p + 1))} disabled={page === data.total_pages}
              className="px-3 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 disabled:opacity-40 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors">
              Next
            </button>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {detailLead && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setDetailLead(null)} />
          <LeadDetailPanel
            lead={detailLead}
            lists={lists}
            onClose={() => setDetailLead(null)}
            onLeadUpdated={handleLeadUpdated}
          />
        </>
      )}
    </>
  );
}
