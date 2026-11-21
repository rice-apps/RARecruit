"use client";

import { useEffect, useState } from "react";
import {
  applicants,
  GRADES_STORAGE_KEY,
  responseScoreFor,
  writtenFullyScored,
  writtenMaxFor,
  type Grade,
} from "@/lib/grading";

type Decision = "undecided" | "papercut" | "interview";

// mock role of the logged-in user. Replace with `role` from GET /me once auth is wired up.
const role: string = "board";

// Highest possible written response score, used as the max for the score filter.
const maxScore = Math.max(...applicants.map(writtenMaxFor));

const card =
  "rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-4 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-6";
const control = "h-9 rounded-[4px] border border-[rgba(15,0,0,0.2)] bg-white px-2 text-sm";
const button =
  "h-9 cursor-pointer rounded-[4px] border border-[#212529] px-3 font-(family-name:--font-pixel) text-sm " +
  "transition-colors disabled:cursor-not-allowed disabled:opacity-40";

export default function ApplicantsPage() {
  const [grades, setGrades] = useState<Record<string, Grade>>({});
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [sortBy, setSortBy] = useState<"score" | "name">("score");
  const [minScore, setMinScore] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Load the grades saved by the Written Applications page (same browser only, until there's a backend).
  // Done after mount because localStorage doesn't exist when the page is pre-rendered on the server.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(GRADES_STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time load from browser storage
      if (saved) setGrades(JSON.parse(saved));
    } catch {
      /* Ignore unavailable or invalid local storage. */
    }
  }, []);

  // Only the board can see this page. TODO: the backend must also enforce this.
  if (role !== "board") {
    return (
      <main className="mx-auto max-w-[1158px] px-6 pb-16 pt-6">
        <p>Only board members can view this page.</p>
      </main>
    );
  }

  // One row per applicant. Score = written response grade only (this page decides who gets an
  // interview), shown once every written response has been scored.
  const rows = applicants.map((a) => {
    const grade = grades[a.id];
    return {
      id: a.id,
      name: a.name,
      score: grade && writtenFullyScored(a, grade) ? responseScoreFor(grade) : null,
      max: writtenMaxFor(a),
      decision: decisions[a.id] ?? "undecided",
    };
  });

  // Rows shown after filtering and sorting. Ungraded applicants sort last.
  const visible = rows
    .filter((r) => minScore === 0 || (r.score !== null && r.score >= minScore))
    .sort((a, b) =>
      sortBy === "score" ? (b.score ?? -1) - (a.score ?? -1) : a.name.localeCompare(b.name),
    );

  // Bulk actions only apply to selected rows that are currently visible.
  const selectedVisible = visible.filter((r) => selected.has(r.id));
  const allSelected = visible.length > 0 && selectedVisible.length === visible.length;

  function toggleOne(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(visible.map((r) => r.id)));
  }

  // Set the decision for the given applicants. TODO: save to the backend.
  function setDecision(ids: string[], decision: Decision) {
    const next = { ...decisions };
    for (const id of ids) next[id] = decision;
    setDecisions(next);
  }

  function bulkSet(decision: Decision) {
    setDecision(selectedVisible.map((r) => r.id), decision);
    setSelected(new Set());
  }

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      <div>
        <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; board /&gt;</p>
        <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">Applicants</h1>
      </div>

      <section className={card}>
        {/* Sort, filter and bulk actions */}
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            Sort by
            <select className={control} value={sortBy} onChange={(e) => setSortBy(e.target.value as "score" | "name")}>
              <option value="score">Score (high to low)</option>
              <option value="name">Name (A to Z)</option>
            </select>
          </label>

          <label className="flex items-center gap-2 text-sm">
            Min score
            <input
              type="number"
              min={0}
              max={maxScore}
              className={`${control} w-20`}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            />
          </label>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-neutral-500">{selectedVisible.length} selected</span>
            <button
              className={`${button} bg-white text-[#212529] hover:bg-neutral-100`}
              disabled={selectedVisible.length === 0}
              onClick={() => bulkSet("papercut")}
            >
              Mark papercut
            </button>
            <button
              className={`${button} bg-[#212529] text-white hover:bg-[#212529]/85`}
              disabled={selectedVisible.length === 0}
              onClick={() => bulkSet("interview")}
            >
              Mark interview
            </button>
          </div>
        </div>

        {/* Applicant table */}
        <div className="overflow-x-auto rounded-xl border border-[rgba(15,0,0,0.12)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 font-(family-name:--font-pixel) text-neutral-500">
              <tr>
                <th className="w-10 px-4 py-3">
                  <input type="checkbox" aria-label="Select all" checked={allSelected} onChange={toggleAll} />
                </th>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Decision</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgba(15,0,0,0.08)]">
              {visible.map((r) => (
                <tr key={r.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.name}`}
                      checked={selected.has(r.id)}
                      onChange={() => toggleOne(r.id)}
                    />
                  </td>
                  <td className="px-4 py-3">{r.name}</td>
                  <td className="px-4 py-3 font-(family-name:--font-pixel)">
                    {r.score === null ? <span className="text-neutral-400">Not graded</span> : `${r.score} / ${r.max}`}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className={control}
                      value={r.decision}
                      onChange={(e) => setDecision([r.id], e.target.value as Decision)}
                    >
                      <option value="undecided">Undecided</option>
                      <option value="papercut">Papercut</option>
                      <option value="interview">Interview</option>
                    </select>
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-neutral-500">
                    No applicants match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
