"use client";

import { useEffect, useState } from "react";

type PanelMember = { id: string; name: string };
type Booking = {
  id: string;
  candidate_id: string;
  candidate_name: string;
  start: string;
  end: string;
  timezone: string;
  status: "confirmed" | "cancelled";
  interviewers: PanelMember[];
  location: string | null;
};
type Candidate = { id: string; name: string; email: string };
type InterviewerLoad = { id: string; name: string | null; load: number };
type Overview = {
  timezone: string;
  bookings: Booking[];
  unbooked_candidates: Candidate[];
  interviewer_loads: InterviewerLoad[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const adminUserId = process.env.NEXT_PUBLIC_ADMIN_USER_ID ?? "admin";

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
  }).format(new Date(value));
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    headers: { "X-User-Id": adminUserId },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const sampleOverview: Overview = {
  timezone: "America/Chicago",
  bookings: [
    {
      id: "booking-c1",
      candidate_id: "c1",
      candidate_name: "Alex",
      start: "2026-12-01T15:00:00Z",
      end: "2026-12-01T15:30:00Z",
      timezone: "America/Chicago",
      status: "confirmed",
      interviewers: [
        { id: "i1", name: "Ana" },
        { id: "i2", name: "Ben" },
      ],
      location: null,
    },
    {
      id: "booking-c2",
      candidate_id: "c2",
      candidate_name: "Blair",
      start: "2026-12-01T16:00:00Z",
      end: "2026-12-01T16:30:00Z",
      timezone: "America/Chicago",
      status: "confirmed",
      interviewers: [
        { id: "i1", name: "Ana" },
        { id: "i3", name: "Chi" },
      ],
      location: null,
    },
  ],
  unbooked_candidates: [
    { id: "c3", name: "Casey", email: "casey@example.com" },
    { id: "c4", name: "Drew", email: "drew@example.com" },
  ],
  interviewer_loads: [
    { id: "i1", name: "Ana", load: 2 },
    { id: "i2", name: "Ben", load: 1 },
    { id: "i3", name: "Chi", load: 1 },
  ],
};

export default function AdminBookingsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    request<Overview>("/admin/bookings")
      .then(setOverview)
      .catch((err: Error) => {
        // Demo data only when the API is unreachable (fetch throws TypeError).
        // Real HTTP errors (403, 500) must surface, not be masked by samples.
        if (err instanceof TypeError) setOverview(sampleOverview);
        else setError(err);
      });
  }, []);

  async function exportCsv() {
    const response = await fetch(`${apiUrl}/admin/bookings.csv`, {
      headers: { "X-User-Id": adminUserId },
    });
    if (!response.ok) {
      setError(new Error("Unable to export bookings."));
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "bookings.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6 sm:p-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">
            Administration
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Bookings</h1>
        </div>
        <button
          className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50"
          onClick={exportCsv}
        >
          Export CSV
        </button>
      </header>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
          <p className="font-medium">Unable to load bookings.</p>
          <p className="mt-1 text-sm">{error.message}</p>
        </div>
      ) : null}
      {overview === null && !error ? <p className="text-zinc-500">Loading bookings...</p> : null}

      {overview ? (
        <>
          <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
            <h2 className="px-5 py-4 text-lg font-semibold">Bookings</h2>
            {overview.bookings.length === 0 ? (
              <p className="border-t border-zinc-100 px-5 py-8 text-center text-zinc-500">
                No bookings have been made.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                    <tr>
                      <th className="px-5 py-3">Candidate</th>
                      <th className="px-5 py-3">Time</th>
                      <th className="px-5 py-3">Interviewers</th>
                      <th className="px-5 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {overview.bookings.map((booking) => (
                      <tr key={booking.id} className="hover:bg-zinc-50">
                        <td className="px-5 py-4 font-medium">{booking.candidate_name}</td>
                        <td className="px-5 py-4">
                          {formatTime(booking.start, booking.timezone)}
                          <span className="mt-1 block text-xs text-zinc-500">
                            Until {formatTime(booking.end, booking.timezone)}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          {booking.interviewers.map((member) => member.name).join(", ")}
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                              booking.status === "confirmed"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-zinc-100 text-zinc-600"
                            }`}
                          >
                            {booking.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <article className="rounded-xl border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Candidates without bookings</h2>
              {overview.unbooked_candidates.length === 0 ? (
                <p className="mt-3 text-sm text-zinc-500">Everyone is booked.</p>
              ) : (
                <ul className="mt-3 divide-y divide-zinc-100">
                  {overview.unbooked_candidates.map((candidate) => (
                    <li className="py-3 text-sm" key={candidate.id}>
                      <span className="font-medium">{candidate.name}</span>
                      <span className="ml-2 text-zinc-500">{candidate.email}</span>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="rounded-xl border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Interviewer load</h2>
              <ul className="mt-3 divide-y divide-zinc-100">
                {overview.interviewer_loads.map((interviewer) => (
                  <li className="flex justify-between py-3 text-sm" key={interviewer.id}>
                    <span>{interviewer.name ?? interviewer.id}</span>
                    <span className="font-semibold">{interviewer.load}</span>
                  </li>
                ))}
              </ul>
            </article>
          </section>
        </>
      ) : null}
    </main>
  );
}
