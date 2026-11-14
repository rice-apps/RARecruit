"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export type RunSummary = {
  id: string;
  status: string;
  phase: string;
  timezone: string;
  created_at: string;
  scheduled_count: number;
  unscheduled_count: number;
  max_interviewer_load: number;
};

export type RunDetail = {
  id: string;
  status: string;
  phase: string;
  timezone: string;
  created_at: string;
  interviews: {
    candidate_id: string;
    candidate_name: string | null;
    start: string;
    end: string;
    interviewers: { id: string; name: string }[];
  }[];
  unscheduled_candidates: { id: string; name: string; email: string }[];
  interviewer_loads: { id: string; name: string | null; load: number }[];
};

type PublishResponse = {
  run: RunDetail;
  emails_sent: number;
  emails_written: number;
  emails_skipped: number;
  email_failures: string[];
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: {
      "X-User-Id": adminUserId,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(
      body?.detail ?? `Request failed with status ${response.status}`,
    );
    error.name = String(response.status);
    throw error;
  }
  return response.json() as Promise<T>;
}

function ErrorState({ error }: { error: Error }) {
  const status = Number(error.name);
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
      <p className="font-medium">
        {status === 403
          ? "You do not have permission to review runs."
          : status === 409
            ? "This run cannot be published in the current phase."
            : "Unable to load schedule runs."}
      </p>
      <p className="mt-1 text-sm">{error.message}</p>
    </div>
  );
}

export function RunsList() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    request<RunSummary[]>("/schedule/runs")
      .then(setRuns)
      .catch(setError);
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6 sm:p-10">
      <header>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">
          Administration
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Schedule runs</h1>
        <p className="mt-2 text-zinc-600">
          Review solver output, compare interviewer balance, and publish one run.
        </p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {runs === null && !error ? (
        <p className="text-zinc-500">Loading schedule runs...</p>
      ) : null}
      {runs?.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-zinc-600">
          No schedule runs have been created yet.
        </div>
      ) : null}
      {runs && runs.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3">Created</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Scheduled</th>
                  <th className="px-5 py-3">Unscheduled</th>
                  <th className="px-5 py-3">Max load</th>
                  <th className="px-5 py-3">Review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-zinc-50">
                    <td className="px-5 py-4">
                      {formatTime(run.created_at, run.timezone)}
                      <span className="mt-1 block text-xs text-zinc-500">
                        {run.timezone}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium">
                        {run.status}
                      </span>
                    </td>
                    <td className="px-5 py-4">{run.scheduled_count}</td>
                    <td className="px-5 py-4">{run.unscheduled_count}</td>
                    <td className="px-5 py-4">{run.max_interviewer_load}</td>
                    <td className="px-5 py-4">
                      <Link
                        className="font-medium text-indigo-700 hover:underline"
                        href={`/admin/runs/${run.id}`}
                      >
                        View run
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export function RunReview({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<PublishResponse | null>(null);

  useEffect(() => {
    request<RunDetail>(`/schedule/runs/${encodeURIComponent(runId)}`)
      .then(setRun)
      .catch(setError);
  }, [runId]);

  async function publish() {
    setPublishing(true);
    setError(null);
    try {
      const result = await request<PublishResponse>(
        `/schedule/runs/${encodeURIComponent(runId)}/publish`,
        { method: "POST" },
      );
      setRun(result.run);
      setPublishResult(result);
      setConfirming(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error("Publish failed"));
    } finally {
      setPublishing(false);
    }
  }

  if (error && !run) {
    return (
      <main className="mx-auto w-full max-w-6xl p-6 sm:p-10">
        <ErrorState error={error} />
      </main>
    );
  }
  if (!run) {
    return (
      <main className="mx-auto w-full max-w-6xl p-6 sm:p-10">
        <p className="text-zinc-500">Loading run review...</p>
      </main>
    );
  }

  const canPublish = run.status !== "published" && run.phase === "solving";
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6 sm:p-10">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link className="text-sm text-indigo-700 hover:underline" href="/admin/runs">
            ← All runs
          </Link>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">Run review</h1>
          <p className="mt-2 text-sm text-zinc-600">
            Created {formatTime(run.created_at, run.timezone)} · {run.timezone} · phase{" "}
            {run.phase}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50"
            href={`/admin/runs/${run.id}/edit`}
          >
            Open edit panel
          </Link>
          {run.status === "published" ? (
            <span className="rounded-lg bg-emerald-100 px-4 py-2 text-sm font-medium text-emerald-800">
              Published
            </span>
          ) : confirming ? (
            <span className="flex gap-2">
              <button
                className="rounded-lg bg-indigo-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                disabled={publishing}
                onClick={publish}
              >
                {publishing ? "Publishing..." : "Confirm publish"}
              </button>
              <button
                className="rounded-lg border border-zinc-300 px-4 py-2 text-sm"
                disabled={publishing}
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              className="rounded-lg bg-indigo-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-300"
              disabled={!canPublish}
              onClick={() => setConfirming(true)}
              title={canPublish ? undefined : "Publishing is available only during solving."}
            >
              Publish run
            </button>
          )}
        </div>
      </header>

      {error ? <ErrorState error={error} /> : null}
      {publishResult ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-medium">Publish completed.</p>
          <p className="mt-1">
            {publishResult.emails_written > 0
              ? `Dry run: ${publishResult.emails_written} email(s) written to the outbox.`
              : `${publishResult.emails_sent} email(s) sent.`}
            {publishResult.emails_skipped > 0
              ? ` ${publishResult.emails_skipped} skipped.`
              : ""}
          </p>
          {publishResult.email_failures.length > 0 ? (
            <p className="mt-1 text-red-700">
              Failures: {publishResult.email_failures.join("; ")}
            </p>
          ) : null}
        </div>
      ) : null}

      <section>
        <h2 className="text-xl font-semibold">Interviews</h2>
        {run.interviews.length === 0 ? (
          <p className="mt-3 text-zinc-500">No interviews in this run.</p>
        ) : (
          <div className="mt-3 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="px-5 py-3">Candidate</th>
                    <th className="px-5 py-3">Time</th>
                    <th className="px-5 py-3">Panel</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {run.interviews.map((interview) => (
                    <tr key={`${interview.candidate_id}-${interview.start}`}>
                      <td className="px-5 py-4 font-medium">
                        {interview.candidate_name ?? interview.candidate_id}
                      </td>
                      <td className="px-5 py-4">
                        {formatTime(interview.start, run.timezone)}
                        <span className="block text-xs text-zinc-500">
                          to {formatTime(interview.end, run.timezone)}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        {interview.interviewers.map((person) => person.name).join(", ") ||
                          "No names available"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="text-xl font-semibold">Unscheduled candidates</h2>
          {run.unscheduled_candidates.length === 0 ? (
            <p className="mt-3 text-zinc-500">Everyone was scheduled.</p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border border-zinc-200 bg-white">
              {run.unscheduled_candidates.map((candidate) => (
                <li className="px-5 py-4" key={candidate.id}>
                  <p className="font-medium">{candidate.name}</p>
                  <p className="text-sm text-zinc-500">{candidate.email}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h2 className="text-xl font-semibold">Interviewer load</h2>
          <ul className="mt-3 divide-y rounded-xl border border-zinc-200 bg-white">
            {run.interviewer_loads.map((person) => (
              <li className="flex items-center justify-between px-5 py-4" key={person.id}>
                <span>{person.name ?? person.id}</span>
                <span className="rounded-full bg-indigo-50 px-3 py-1 text-sm font-semibold text-indigo-800">
                  {person.load}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
