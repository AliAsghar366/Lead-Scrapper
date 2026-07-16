"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LeadList, SavedSearch } from "@/types";

interface Props {
  activeListId: number | null;
  onSelectList: (id: number | null) => void;
  onRunSearch: (query: string) => void;
}

export default function LeadListsPanel({ activeListId, onSelectList, onRunSearch }: Props) {
  const [lists, setLists] = useState<LeadList[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [creatingList, setCreatingList] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [newListColor, setNewListColor] = useState("#3b82f6");

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

  useEffect(() => {
    api.getLists().then(setLists).catch(() => {});
    api.getSavedSearches().then(setSavedSearches).catch(() => {});
  }, []);

  async function handleCreateList() {
    if (!newListName.trim()) return;
    const lst = await api.createList(newListName.trim(), "", newListColor);
    setLists([lst, ...lists]);
    setNewListName("");
    setCreatingList(false);
  }

  async function handleDeleteList(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    await api.deleteList(id);
    setLists(lists.filter(l => l.id !== id));
    if (activeListId === id) onSelectList(null);
  }

  async function handleDeleteSavedSearch(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    await api.deleteSavedSearch(id);
    setSavedSearches(savedSearches.filter(s => s.id !== id));
  }

  return (
    <div className="w-56 flex-shrink-0 space-y-5">
      {/* Lead Lists */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Lists</h3>
          <button onClick={() => setCreatingList(!creatingList)}
            className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 font-medium">
            + New
          </button>
        </div>

        {creatingList && (
          <div className="mb-2 p-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 space-y-2">
            <input
              autoFocus
              value={newListName}
              onChange={e => setNewListName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreateList()}
              placeholder="List name…"
              className="w-full text-xs px-2 py-1.5 rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <div className="flex gap-1.5">
              {COLORS.map(c => (
                <button key={c} onClick={() => setNewListColor(c)}
                  style={{ background: c }}
                  className={`w-5 h-5 rounded-full transition-transform ${newListColor === c ? "scale-125 ring-2 ring-offset-1 ring-zinc-400" : ""}`}
                />
              ))}
            </div>
            <div className="flex gap-1.5">
              <button onClick={handleCreateList}
                className="flex-1 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors">
                Create
              </button>
              <button onClick={() => setCreatingList(false)}
                className="flex-1 py-1 text-xs border border-zinc-300 dark:border-zinc-600 rounded text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="space-y-0.5">
          <button
            onClick={() => onSelectList(null)}
            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors text-left ${
              activeListId === null
                ? "bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-medium"
                : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            }`}>
            <span className="text-base">📋</span> All Leads
          </button>
          {lists.map(lst => (
            <button key={lst.id}
              onClick={() => onSelectList(lst.id)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors text-left group ${
                activeListId === lst.id
                  ? "bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-medium"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}>
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: lst.color }} />
              <span className="flex-1 truncate">{lst.name}</span>
              <span className="text-zinc-400 text-xs">{lst.member_count}</span>
              <span onClick={e => handleDeleteList(lst.id, e)}
                className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-500 transition-all ml-0.5">✕</span>
            </button>
          ))}
        </div>
      </div>

      {/* Saved Searches */}
      <div>
        <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
          Saved Searches
        </h3>
        <div className="space-y-0.5">
          {savedSearches.length === 0 && (
            <p className="text-xs text-zinc-400 px-2 py-2">None saved yet.<br/>Use the search box and save.</p>
          )}
          {savedSearches.map(ss => (
            <button key={ss.id}
              onClick={() => onRunSearch(ss.query)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-left text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors group">
              <span className="text-base">🔍</span>
              <span className="flex-1 truncate">{ss.name}</span>
              <span onClick={e => handleDeleteSavedSearch(ss.id, e)}
                className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-500 transition-all">✕</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
