"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { safeUrl } from "@/lib/utils";
import type { Lead, LeadNote, ActivityLog, LeadStatus, LeadList } from "@/types";

const STATUS_OPTIONS: { value: LeadStatus; label: string; color: string }[] = [
  { value: "new",       label: "New",       color: "bg-zinc-100 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200" },
  { value: "contacted", label: "Contacted", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200" },
  { value: "qualified", label: "Qualified", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200" },
  { value: "rejected",  label: "Rejected",  color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200" },
  { value: "won",       label: "Won",       color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200" },
  { value: "lost",      label: "Lost",      color: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-200" },
];

function StatusBadge({ status }: { status: LeadStatus }) {
  const opt = STATUS_OPTIONS.find(s => s.value === status) ?? STATUS_OPTIONS[0];
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${opt.color}`}>{opt.label}</span>;
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300 w-8 text-right">{score}</span>
    </div>
  );
}

interface Props {
  lead: Lead | null;
  lists: LeadList[];
  onClose: () => void;
  onLeadUpdated: (lead: Lead) => void;
}

export default function LeadDetailPanel({ lead, lists, onClose, onLeadUpdated }: Props) {
  const [notes, setNotes] = useState<LeadNote[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [activity, setActivity] = useState<ActivityLog[]>([]);
  const [newNote, setNewNote] = useState("");
  const [newTag, setNewTag] = useState("");
  const [tab, setTab] = useState<"info" | "notes" | "tags" | "activity">("info");
  const [verifying, setVerifying] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentLead, setCurrentLead] = useState<Lead | null>(lead);

  useEffect(() => {
    setCurrentLead(lead);
    setTab("info");
    if (!lead) return;
    api.getNotes(lead.id).then(setNotes).catch(() => {});
    api.getTags(lead.id).then(setTags).catch(() => {});
    api.getActivity(lead.id).then(setActivity).catch(() => {});
  }, [lead?.id]);

  if (!currentLead) return null;

  async function handleStatus(status: LeadStatus) {
    if (!currentLead) return;
    setSaving(true);
    try {
      const updated = await api.setStatus(currentLead.id, status);
      setCurrentLead(updated);
      onLeadUpdated(updated);
      const logs = await api.getActivity(currentLead.id);
      setActivity(logs);
    } finally { setSaving(false); }
  }

  async function handleAddNote() {
    if (!newNote.trim() || !currentLead) return;
    const note = await api.addNote(currentLead.id, newNote.trim());
    setNotes([note, ...notes]);
    setNewNote("");
    const logs = await api.getActivity(currentLead.id);
    setActivity(logs);
  }

  async function handleDeleteNote(noteId: number) {
    if (!currentLead) return;
    await api.deleteNote(currentLead.id, noteId);
    setNotes(notes.filter(n => n.id !== noteId));
  }

  async function handleAddTag() {
    if (!newTag.trim() || !currentLead) return;
    const res = await api.addTag(currentLead.id, newTag.trim());
    setTags(res.tags);
    setNewTag("");
  }

  async function handleRemoveTag(tag: string) {
    if (!currentLead) return;
    const res = await api.removeTag(currentLead.id, tag);
    setTags(res.tags);
  }

  async function handleVerifyEmail() {
    if (!currentLead) return;
    setVerifying(true);
    try {
      const res = await api.verifyEmail(currentLead.id);
      const updated = await api.getLead(currentLead.id);
      setCurrentLead(updated);
      onLeadUpdated(updated);
      const logs = await api.getActivity(currentLead.id);
      setActivity(logs);
    } finally { setVerifying(false); }
  }

  async function handleEnrichLinkedIn() {
    if (!currentLead) return;
    setEnriching(true);
    try {
      const updated = await api.enrichLinkedIn(currentLead.id);
      setCurrentLead(updated);
      onLeadUpdated(updated);
      const logs = await api.getActivity(currentLead.id);
      setActivity(logs);
    } finally { setEnriching(false); }
  }

  async function handleAddToList(listId: number) {
    if (!currentLead) return;
    await api.addLeadsToList(listId, [currentLead.id]);
  }

  const link = (href: string | null, label: string) => {
    if (!href) return <span className="text-zinc-400">—</span>;
    return <a href={safeUrl(href) ?? "#"} target="_blank" rel="noopener noreferrer"
      className="text-blue-600 dark:text-blue-400 hover:underline truncate">{label}</a>;
  };

  const field = (label: string, value: string | null | undefined) => (
    <div className="grid grid-cols-5 gap-2 py-1.5 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
      <span className="col-span-2 text-xs text-zinc-400 font-medium pt-0.5">{label}</span>
      <span className="col-span-3 text-xs text-zinc-800 dark:text-zinc-200 break-all">{value || "—"}</span>
    </div>
  );

  return (
    <div className="fixed inset-y-0 right-0 w-[420px] bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-700 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-zinc-200 dark:border-zinc-700">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="font-bold text-base text-zinc-900 dark:text-zinc-100 truncate">
              {currentLead.name || "Unnamed Lead"}
            </h2>
            <p className="text-xs text-zinc-500 capitalize mt-0.5">{currentLead.category || "—"}</p>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 text-xl leading-none mt-0.5">✕</button>
        </div>

        {/* Score bar */}
        <div className="mt-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-zinc-500">Lead Score</span>
            <StatusBadge status={currentLead.status} />
          </div>
          <ScoreBar score={currentLead.score} />
        </div>

        {/* Status picker */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {STATUS_OPTIONS.map(opt => (
            <button key={opt.value}
              onClick={() => handleStatus(opt.value)}
              disabled={saving}
              className={`px-2.5 py-1 rounded-full text-xs border transition-all ${
                currentLead.status === opt.value
                  ? `${opt.color} border-transparent font-semibold`
                  : "border-zinc-200 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400 hover:border-zinc-400"
              }`}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-200 dark:border-zinc-700">
        {(["info", "notes", "tags", "activity"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-medium capitalize transition-colors ${
              tab === t
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}>
            {t}{t === "notes" && notes.length > 0 ? ` (${notes.length})` : ""}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-5">

        {tab === "info" && (
          <div className="space-y-4">
            {/* Quick actions */}
            <div className="flex flex-wrap gap-2">
              <button onClick={handleVerifyEmail} disabled={verifying || !currentLead.email}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors">
                {verifying ? "Verifying…" : currentLead.email_verified === true ? "✓ Email Valid"
                  : currentLead.email_verified === false ? "✗ Email Invalid" : "Verify Email"}
              </button>
              <button onClick={handleEnrichLinkedIn} disabled={enriching || !currentLead.name}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-blue-300 text-blue-600 dark:border-blue-700 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-40 transition-colors">
                {enriching ? "Enriching…" : "Enrich via LinkedIn"}
              </button>
            </div>

            {/* Add to list */}
            {lists.length > 0 && (
              <div>
                <p className="text-xs font-medium text-zinc-500 mb-1.5">Add to list</p>
                <div className="flex flex-wrap gap-1.5">
                  {lists.map(lst => (
                    <button key={lst.id} onClick={() => handleAddToList(lst.id)}
                      style={{ borderColor: lst.color, color: lst.color }}
                      className="px-2.5 py-1 text-xs rounded-full border hover:opacity-80 transition-opacity">
                      + {lst.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Contact info */}
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-2">Contact</p>
              <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg px-3 py-1">
                <div className="grid grid-cols-5 gap-2 py-1.5 border-b border-zinc-100 dark:border-zinc-800">
                  <span className="col-span-2 text-xs text-zinc-400 font-medium">Website</span>
                  <span className="col-span-3 text-xs">{link(currentLead.website, currentLead.website ? new URL(currentLead.website).hostname : "—")}</span>
                </div>
                {field("Email", currentLead.email)}
                {field("Phone", currentLead.phone)}
                {field("Address", currentLead.address)}
              </div>
            </div>

            {/* Company info */}
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-2">Company</p>
              <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg px-3 py-1">
                {field("Industry", currentLead.industry)}
                {field("Employees", currentLead.employee_count)}
                {field("Founded", currentLead.founded_year)}
                {field("City", currentLead.city)}
                {field("Country", currentLead.country)}
              </div>
            </div>

            {/* Social */}
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-2">Social</p>
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "linkedin", label: "LinkedIn" },
                  { key: "facebook", label: "Facebook" },
                  { key: "instagram", label: "Instagram" },
                  { key: "twitter", label: "Twitter/X" },
                  { key: "youtube", label: "YouTube" },
                ].map(({ key, label }) => {
                  const val = currentLead[key as keyof Lead] as string | null;
                  return val ? (
                    <a key={key} href={safeUrl(val) ?? "#"} target="_blank" rel="noopener noreferrer"
                      className="px-2.5 py-1 text-xs rounded-full border border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-300 hover:border-blue-400 hover:text-blue-600 transition-colors">
                      {label}
                    </a>
                  ) : null;
                })}
              </div>
            </div>

            {currentLead.description && (
              <div>
                <p className="text-xs font-medium text-zinc-500 mb-2">Description</p>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">{currentLead.description}</p>
              </div>
            )}
          </div>
        )}

        {tab === "notes" && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <textarea
                value={newNote}
                onChange={e => setNewNote(e.target.value)}
                placeholder="Add a note…"
                rows={3}
                className="flex-1 text-xs px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-800 dark:text-zinc-100 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button onClick={handleAddNote}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg self-end transition-colors">
                Add
              </button>
            </div>
            {notes.length === 0 && (
              <p className="text-xs text-zinc-400 text-center py-6">No notes yet</p>
            )}
            {notes.map(note => (
              <div key={note.id} className="group relative bg-zinc-50 dark:bg-zinc-800 rounded-lg p-3">
                <p className="text-xs text-zinc-700 dark:text-zinc-200 leading-relaxed whitespace-pre-wrap">{note.content}</p>
                <p className="text-xs text-zinc-400 mt-2">
                  {note.created_at ? new Date(note.created_at).toLocaleString() : ""}
                </p>
                <button onClick={() => handleDeleteNote(note.id)}
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-500 text-xs transition-all">
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {tab === "tags" && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                value={newTag}
                onChange={e => setNewTag(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleAddTag()}
                placeholder="Add tag (Enter to save)"
                className="flex-1 text-xs px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button onClick={handleAddTag}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg transition-colors">
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {tags.map(tag => (
                <span key={tag} className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 rounded-full text-xs border border-blue-200 dark:border-blue-800">
                  {tag}
                  <button onClick={() => handleRemoveTag(tag)}
                    className="text-blue-400 hover:text-red-500 leading-none transition-colors">✕</button>
                </span>
              ))}
              {tags.length === 0 && (
                <p className="text-xs text-zinc-400 py-6 w-full text-center">No tags yet</p>
              )}
            </div>
          </div>
        )}

        {tab === "activity" && (
          <div className="space-y-2">
            {activity.length === 0 && (
              <p className="text-xs text-zinc-400 text-center py-6">No activity yet</p>
            )}
            {activity.map(log => (
              <div key={log.id} className="flex gap-3 py-2 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs">
                    {log.action === "status_changed" ? "⚡" :
                     log.action === "note_added" ? "📝" :
                     log.action === "tagged" ? "🏷" :
                     log.action === "email_verified" ? "✉" :
                     log.action === "linkedin_enriched" ? "💼" : "•"}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-zinc-700 dark:text-zinc-200 capitalize">
                    {log.action.replace(/_/g, " ")}
                  </p>
                  {log.detail && <p className="text-xs text-zinc-400 truncate">{log.detail}</p>}
                  <p className="text-xs text-zinc-400 mt-0.5">
                    {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
