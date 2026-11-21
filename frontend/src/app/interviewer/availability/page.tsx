"use client";
// Availability page: a weekly grid of 30-min slots the interviewer clicks or drags to mark free time.
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

// diagonal stripes for slots for dates in the past so they can't be edited
const PAST_BG = "bg-[repeating-linear-gradient(135deg,#eef0f2_0px,#eef0f2_4px,#ffffff_4px,#ffffff_8px)]";

// Indexed by Date.getDay() (0 = Sunday).
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
// Grid shows 7 AM to 10 PM.
const START_HOUR = 7;
const END_HOUR = 22;

// 30-minute slot start times, stored as "HH:MM"
const TIMES: string[] = [];
for (let m = START_HOUR * 60; m < END_HOUR * 60; m += 30) {
  TIMES.push(`${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);
}

// Date helpers. A slot is stored as a string like "2026-11-21T09:30".
const pad = (n: number) => String(n).padStart(2, "0");
// Local date as "YYYY-MM-DD" (not toISOString, which would shift to UTC).
const toKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const slotKey = (date: string, time: string) => `${date}T${time}`;

function addDays(d: Date, n: number) {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

// Sunday 00:00 of the week containing d.
function startOfWeek(d: Date) {
  const copy = new Date(d);
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - copy.getDay());
  return copy;
}

// 13 -> "1 PM"
function formatHour(h: number) {
  return `${h % 12 || 12} ${h >= 12 ? "PM" : "AM"}`;
}

// mock initial data: weekdays 9–12 and 1–5 for the next 3 weeks that can replaced with backend info
function mockSlots(): Set<string> {
  const s = new Set<string>();
  const week = startOfWeek(new Date());
  for (let i = 0; i < 21; i++) {
    const d = addDays(week, i);
    if (d.getDay() === 0 || d.getDay() === 6) continue;
    for (const t of TIMES) {
      if ((t >= "09:00" && t < "12:00") || (t >= "13:00" && t < "17:00")) s.add(slotKey(toKey(d), t));
    }
  }
  return s;
}

// Used with useSyncExternalStore below to tell server render vs. browser render apart.
const noopSubscribe = () => () => {};

export default function AvailabilityPage() {
  // The calendar depends on the current date/time, so only render it in the browser
  const isClient = useSyncExternalStore(noopSubscribe, () => true, () => false);

  if (!isClient) {
    return (
      <main className="mx-auto max-w-[1158px] px-6 pb-16 pt-6">
        <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight">Availability</h1>
        <p className="mt-4 text-neutral-500">Loading calendar…</p>
      </main>
    );
  }
  return <AvailabilityCalendar />;
}

function AvailabilityCalendar() {
  const [slots, setSlots] = useState<Set<string>>(mockSlots); // every available slot key, across all weeks
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date())); // week being viewed
  const [saved, setSaved] = useState(true); // false once anything changes

  // drag-to-paint state: whether we're adding or removing slots like when2meet
  const dragMode = useRef<"add" | "remove" | null>(null);

  const now = new Date();
  const thisWeek = startOfWeek(now);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  // Slots before right now are locked.
  const isPast = (date: Date, time: string) => {
    const [h, m] = time.split(":").map(Number);
    const d = new Date(date);
    d.setHours(h, m, 0, 0);
    return d < now;
  };

  // Stop painting when the mouse/finger is released anywhere on the page, not just on the grid.
  useEffect(() => {
    const end = () => (dragMode.current = null);
    window.addEventListener("pointerup", end);
    return () => window.removeEventListener("pointerup", end);
  }, []);

  // Add or remove one slot, depending on the current drag mode.
  const paint = (key: string) => {
    if (!dragMode.current) return;
    setSlots((prev) => {
      const has = prev.has(key);
      // already in the state we want: return prev unchanged so React skips a re-render
      if ((dragMode.current === "add") === has) return prev;
      const next = new Set(prev);
      if (dragMode.current === "add") next.add(key);
      else next.delete(key);
      return next;
    });
    setSaved(false);
  };

  // Starting on an empty slot means "add" for the whole drag; starting on a filled one means "remove".
  const onPointerDown = (e: React.PointerEvent, key: string) => {
    e.preventDefault(); // stops text selection while dragging
    dragMode.current = slots.has(key) ? "remove" : "add";
    paint(key);
  };

  // Pointer move on the grid. Uses elementFromPoint because on touch screens the
  // events stay on the cell where the drag started; data-slot says which slot is under the finger.
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragMode.current) return;
    const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null;
    const key = el?.dataset.slot;
    if (key) paint(key);
  };

  // Runs fn for each day of the visible week on a copy of slots, then saves the copy.
  const updateWeek = (fn: (next: Set<string>, date: string) => void) => {
    setSlots((prev) => {
      const next = new Set(prev);
      days.forEach((d) => fn(next, toKey(d)));
      return next;
    });
    setSaved(false);
  };

  // Clear Week / Copy Last Week both leave past slots alone.
  const clearWeek = () =>
    updateWeek((next, date) => TIMES.forEach((t) => {
      if (!isPast(new Date(`${date}T00:00:00`), t)) next.delete(slotKey(date, t));
    }));

  const copyPrevWeek = () =>
    updateWeek((next, date) => {
      const prevDate = toKey(addDays(new Date(`${date}T00:00:00`), -7));
      TIMES.forEach((t) => {
        if (isPast(new Date(`${date}T00:00:00`), t)) return;
        if (slots.has(slotKey(prevDate, t))) next.add(slotKey(date, t));
        else next.delete(slotKey(date, t));
      });
    });

  // Each slot is 30 min, so hours = slot count / 2.
  const hoursFor = (date: Date) =>
    TIMES.filter((t) => slots.has(slotKey(toKey(date), t))).length / 2;
  const weekHours = days.reduce((sum, d) => sum + hoursFor(d), 0);

  const save = () => {
    // can send availability to backend here, but for now just log it to the console
    console.log("Saving availability", [...slots].sort());
    setSaved(true);
  };

  const weekLabel = `${days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; interviewer /&gt;</p>
          <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">Availability</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 text-sm text-neutral-500">
            <span className={`h-2 w-2 rounded-full ${saved ? "bg-emerald-500" : "bg-amber-400"}`} />
            {saved ? "All changes saved" : "Unsaved changes"}
          </span>
          <button
            onClick={save}
            disabled={saved}
            className="rounded-md bg-[#212529] px-5 py-2.5 text-sm text-white transition-colors hover:bg-black disabled:cursor-default disabled:opacity-40 disabled:hover:bg-[#212529]"
          >
            Save Changes
          </button>
        </div>
      </div>

      <section className="rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-4 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {/* can't go back before the current week */}
            <button
              onClick={() => setWeekStart(addDays(weekStart, -7))}
              disabled={weekStart <= thisWeek}
              aria-label="Previous week"
              className="h-9 w-9 rounded-full border border-[rgba(15,0,0,0.12)] transition-colors hover:bg-neutral-100 disabled:cursor-default disabled:opacity-30 disabled:hover:bg-transparent"
            >
              ‹
            </button>
            <button
              onClick={() => setWeekStart(addDays(weekStart, 7))}
              aria-label="Next week"
              className="h-9 w-9 rounded-full border border-[rgba(15,0,0,0.12)] transition-colors hover:bg-neutral-100"
            >
              ›
            </button>
            <button
              onClick={() => setWeekStart(thisWeek)}
              className="h-9 rounded-full border border-[rgba(15,0,0,0.12)] px-4 text-sm transition-colors hover:bg-neutral-100"
            >
              Today
            </button>
            <h2 className="ml-3 font-(family-name:--font-pixel) text-2xl font-medium tracking-tight">{weekLabel}</h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="mr-2 font-(family-name:--font-pixel) text-sm text-neutral-500">{weekHours} hrs this week</span>
            <button onClick={copyPrevWeek} className="h-9 rounded-full border border-[rgba(15,0,0,0.12)] px-4 text-sm transition-colors hover:bg-neutral-100">
              Copy Last Week
            </button>
            <button onClick={clearWeek} className="h-9 rounded-full border border-[rgba(15,0,0,0.12)] px-4 text-sm transition-colors hover:bg-neutral-100">
              Clear Week
            </button>
          </div>
        </div>

        {/* Grid scrolls sideways on small screens. 1st column = time labels, then 7 day columns. */}
        <div className="overflow-x-auto rounded-xl border border-[rgba(15,0,0,0.12)]">
          <div
            className="grid min-w-[640px] select-none touch-none"
            style={{ gridTemplateColumns: "4rem repeat(7, minmax(0, 1fr))" }}
            onPointerMove={onPointerMove}
          >
            {/* header row */}
            {/* corner cell: no bottom border so the 7 AM line stops before its label */}
            <div />
            {days.map((d) => {
              const isToday = toKey(d) === toKey(now);
              return (
                <div key={toKey(d)} className="border-b border-l border-[rgba(15,0,0,0.12)] px-2 py-3 text-center">
                  <div className="font-(family-name:--font-pixel) text-xs uppercase tracking-wider text-neutral-500">{DAY_NAMES[d.getDay()]}</div>
                  <div
                    className={`mx-auto mt-0.5 flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold
                      ${isToday ? "bg-[#212529] text-white" : ""}`}
                  >
                    {d.getDate()}
                  </div>
                  <div className="text-xs text-neutral-400">{hoursFor(d) ? `${hoursFor(d)} hrs` : "—"}</div>
                </div>
              );
            })}

            {/* time rows */}
            {TIMES.map((t) => {
              const onHour = t.endsWith(":00"); // darker line + label on the hour, lighter on the half hour
              return (
                // `contents` drops this wrapper from the layout so its cells sit directly in the grid
                <div key={t} className="contents">
                  <div className="relative pr-2 text-right font-(family-name:--font-pixel) text-[11px] text-neutral-400">
                    {onHour && <span className="absolute -top-2 right-2">{formatHour(Number(t.slice(0, 2)))}</span>}
                  </div>
                  {days.map((d) => {
                    const key = slotKey(toKey(d), t);
                    const past = isPast(d, t);
                    const active = slots.has(key);
                    return (
                      <div
                        key={key}
                        // past slots get no data-slot / handler, so they can't be painted
                        data-slot={past ? undefined : key}
                        onPointerDown={past ? undefined : (e) => onPointerDown(e, key)}
                        title={past ? "This time has passed" : undefined}
                        className={`h-6 border-l border-[rgba(15,0,0,0.12)] ${onHour ? "border-t" : "border-t border-t-neutral-100"}
                          ${past
                            ? `cursor-not-allowed ${active ? "bg-neutral-300" : PAST_BG}`
                            : active ? "cursor-pointer bg-[#212529] hover:bg-black" : "cursor-pointer hover:bg-neutral-100"}`}
                      />
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-5 text-sm text-neutral-500">
          <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#212529]" /> Available</span>
          <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-[rgba(15,0,0,0.2)] bg-white" /> Unavailable</span>
          <span className="flex items-center gap-2"><span className={`h-3 w-3 rounded-sm border border-[rgba(15,0,0,0.2)] ${PAST_BG}`} /> Past (locked)</span>
        </div>
      </section>
    </main>
  );
}
