import Link from "next/link";
import { MAX_SCORE, type Interview } from "@/lib/interviews";

export default function InterviewCard({ interview }: { interview: Interview }) {
  const date = new Date(interview.time);
  const graded = interview.grade !== null;

  return (
    <Link
      href={`/interviewer/interviews/${interview.id}`}
      className="flex flex-col gap-4 rounded-2xl border border-[rgba(15,0,0,0.12)] bg-white p-6 transition-shadow hover:shadow-md"
      style={{ boxShadow: "0px 5px 6.8px rgba(0,0,0,0.04)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-mono text-lg text-neutral-900">{interview.name}</h3>
        <span className="shrink-0 rounded-[4px] bg-neutral-900 px-2 py-0.5 font-mono text-xs text-neutral-100">
          {interview.role}
        </span>
      </div>

      <dl className="grid gap-2 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-neutral-900/60">Program</dt>
          <dd className="text-right text-neutral-900">{interview.program}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-neutral-900/60">Date</dt>
          <dd className="text-neutral-900">
            {date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-neutral-900/60">Time</dt>
          <dd className="text-neutral-900">
            {date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-neutral-900/60">Score</dt>
          <dd className={graded ? "text-neutral-900" : "text-neutral-900/60"}>
            {graded ? `${interview.grade}/${MAX_SCORE}` : "Not graded"}
          </dd>
        </div>
      </dl>
    </Link>
  );
}
