"use client";

import { useEffect, useMemo, useState } from "react";

type MyInterview = {
  status: "scheduled" | "not_scheduled";
  candidate_id: string | null;
  candidate_name: string | null;
  start: string | null;
  end: string | null;
  timezone: string | null;
  panel: { id: string; name: string }[];
  message: string | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const userId = process.env.NEXT_PUBLIC_USER_ID ?? "c1";

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "full",
    timeStyle: "short",
    timeZone: timezone,
  }).format(new Date(value));
}

async function loadInterviews(): Promise<MyInterview[]> {
  const response = await fetch(`${apiUrl}/interviews/me`, {
    headers: { "X-User-Id": userId },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(
      body?.detail ?? `Request failed with status ${response.status}`,
    );
    error.name = String(response.status);
    throw error;
  }
  return response.json() as Promise<MyInterview[]>;
}

function ErrorState({ error }: { error: Error }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
      <p className="font-medium">
        {error.name === "403"
          ? "This page is only available to candidates and interviewers."
          : "Unable to load your interviews."}
      </p>
      <p className="mt-1 text-sm">{error.message}</p>
    </div>
  );
}

export default function MyInterviewPage() {
  const [interviews, setInterviews] = useState<MyInterview[] | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    loadInterviews().then(setInterviews).catch(setError);
  }, []);

  const scheduled = useMemo(
    () =>
      (interviews ?? [])
        .filter(
          (interview): interview is MyInterview & { start: string; end: string } =>
            interview.status === "scheduled" &&
            interview.start !== null &&
            interview.end !== null,
        )
        .sort(
          (left, right) =>
            new Date(left.start).getTime() - new Date(right.start).getTime(),
        ),
    [interviews],
  );

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-6 sm:p-10">
      <header>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">
          RARecruit
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">My interview</h1>
        <p className="mt-2 text-zinc-600">
          Your published interview schedule and panel details.
        </p>
      </header>

      {error ? <ErrorState error={error} /> : null}
      {interviews === null && !error ? (
        <p className="text-zinc-500">Loading your interviews...</p>
      ) : null}

      {interviews?.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center">
          <h2 className="font-semibold">Nothing published yet</h2>
          <p className="mt-2 text-sm text-zinc-600">
            Your interview will appear here after an admin publishes the schedule.
          </p>
        </div>
      ) : null}

      {interviews?.some((interview) => interview.status === "not_scheduled") ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
          <h2 className="font-semibold">Not scheduled</h2>
          <p className="mt-1 text-sm">
            {interviews.find((interview) => interview.status === "not_scheduled")?.message ??
              "You are not scheduled for an interview in the published run."}
          </p>
        </div>
      ) : null}

      {scheduled.length > 0 ? (
        <section>
          <h2 className="text-xl font-semibold">
            {scheduled.length === 1 ? "Your interview" : "Your interviews"}
          </h2>
          <div className="mt-3 grid gap-4">
            {scheduled.map((interview) => {
              const timezone = interview.timezone ?? "UTC";
              return (
                <article
                  className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm"
                  key={`${interview.candidate_id}-${interview.start}`}
                >
                  <p className="text-lg font-semibold">
                    {formatTime(interview.start, timezone)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    Until {formatTime(interview.end, timezone)}
                  </p>
                  <p className="mt-3 text-xs font-medium uppercase tracking-wide text-indigo-700">
                    Timezone: {timezone}
                  </p>
                  <div className="mt-5 border-t border-zinc-100 pt-4">
                    <h3 className="text-sm font-semibold">Panel</h3>
                    {interview.panel.length > 0 ? (
                      <ul className="mt-2 flex flex-wrap gap-2">
                        {interview.panel.map((member) => (
                          <li
                            className="rounded-full bg-zinc-100 px-3 py-1 text-sm"
                            key={member.id}
                          >
                            {member.name}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-zinc-500">
                        Panel details are not available.
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}
    </main>
  );
}
