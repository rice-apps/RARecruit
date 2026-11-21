// Interview detail page at /interviewer/interviews/[id].
// Shows one interview: the embedded grading template on the left and the
// score + summary form on the right (stacked on smaller screens).
//
// This is a Server Component: it loads the data on the server and sends HTML.
// The form needs state and click handlers, so it lives in GradeForm.tsx,
// which is a Client Component ("use client").

import Link from "next/link";
import { notFound } from "next/navigation";
import GradeForm from "./GradeForm";
import { getCurrentInterviewer, getInterview, toEmbedUrl } from "@/lib/interviews";

// `params` holds the [id] part of the URL, e.g. /interviewer/interviews/2 -> { id: "2" }.
// In this version of Next.js it's a Promise, so it has to be awaited.
export default async function InterviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  // Mock user for now (always Mac). Will be the signed-in interviewer once auth exists.
  const interviewer = await getCurrentInterviewer();

  // getInterview returns null both when the id doesn't exist and when the
  // interview belongs to another interviewer, so people can't view someone
  // else's interview by typing its id into the URL. Either way we show a 404.
  const interview = await getInterview(id, interviewer.id);
  if (!interview) notFound();

  const date = new Date(interview.time);

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      {/* Header: back link, candidate name, and role / program / time */}
      <div>
        <Link
          href="/interviewer/interviews"
          className="mb-3 inline-block font-(family-name:--font-pixel) text-sm text-neutral-500 hover:text-neutral-900"
        >
          ← All interviews
        </Link>
        <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">
          {interview.name}
        </h1>
        <p className="mt-3 text-neutral-900/60">
          {interview.role} · {interview.program} ·{" "}
          {/* `undefined` locale = format dates the way the viewer's browser/server prefers */}
          {date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })},{" "}
          {date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
        </p>
      </div>

      {/* Two columns on large screens (template gets 3/5 of the width, form 2/5); one column below that */}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        {/* Left: the Google Doc grading template */}
        <section className="rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-4 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-6">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <h2 className="font-(family-name:--font-pixel) text-2xl font-medium tracking-tight">Grading Template</h2>
            {/* Opens the normal editable doc in a new tab (noopener keeps that tab from controlling this one) */}
            <a
              href={interview.gradingDocUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-(family-name:--font-pixel) text-sm text-neutral-500 hover:text-neutral-900"
            >
              Open in Google Docs ↗
            </a>
          </div>
          {/* Embedded read-only view. toEmbedUrl turns the /edit link into Google's
              /preview link, which is the clean version meant for embedding. The viewer still needs access
              to the doc, or Google shows a "You need access" message here. */}
          <iframe
            src={toEmbedUrl(interview.gradingDocUrl)}
            title={`Grading template for ${interview.name}`}
            className="h-[70vh] w-full rounded-xl border border-[rgba(15,0,0,0.12)]"
          />
        </section>

        {/* Right: score + summary form. h-fit keeps the card only as tall as its contents. */}
        <section className="h-fit rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-4 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-6">
          <h2 className="mb-4 font-(family-name:--font-pixel) text-2xl font-medium tracking-tight">Your Evaluation</h2>
          {/* Pass in any existing score/summary so the form starts filled in */}
          <GradeForm interviewId={interview.id} initialGrade={interview.grade} initialSummary={interview.summary} />
        </section>
      </div>
    </main>
  );
}
