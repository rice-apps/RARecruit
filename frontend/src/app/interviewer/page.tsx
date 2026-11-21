// Interviewer home: greeting, quick links, and upcoming interviews.
import Link from "next/link";
import { getCurrentInterviewer, getInterviewsForInterviewer } from "@/lib/interviews";

// Pixel-font buttons with a hard offset shadow; they lift on hover and the arrow slides right.
const baseButton =
  "group inline-flex h-11 items-center gap-3 rounded-[4px] border px-5 font-(family-name:--font-pixel) text-sm " +
  "transition-all duration-200 hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0 active:translate-y-0";
const primaryButton =
  `${baseButton} border-[#212529] bg-[#212529] text-white shadow-[3px_3px_0_rgba(33,37,41,0.25)] ` +
  "hover:shadow-[5px_5px_0_rgba(33,37,41,0.25)] active:shadow-[1px_1px_0_rgba(33,37,41,0.25)]";
const secondaryButton =
  `${baseButton} border-[rgba(15,0,0,0.2)] bg-white text-[#212529] shadow-[3px_3px_0_rgba(33,37,41,0.12)] ` +
  "hover:border-[#212529] hover:shadow-[5px_5px_0_rgba(33,37,41,0.2)] active:shadow-[1px_1px_0_rgba(33,37,41,0.2)]";

// "→" that slides right when its parent button (the `group`) is hovered.
function Arrow() {
  return (
    <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-1">
      →
    </span>
  );
}

export default async function InterviewerHome() {
  const interviewer = await getCurrentInterviewer();
  const upcoming = await getInterviewsForInterviewer(interviewer.id); // already sorted earliest first

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      <div>
        <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; interviewer /&gt;</p>
        <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">
          Welcome back,{" "}
          {/* first name only */}
          <span className="font-(family-name:--font-pixel) italic">{interviewer.name.split(" ")[0]}</span>
        </h1>
      </div>

      {/* Quick links */}
      <div className="flex flex-wrap gap-4">
        <Link href="/interviewer/availability" className={primaryButton}>
          Edit Availability <Arrow />
        </Link>
        <Link href="/interviewer/applications" className={secondaryButton}>
          Continue Grading <Arrow />
        </Link>
        <Link href="/interviewer/candidates" className={secondaryButton}>
          View Candidates <Arrow />
        </Link>
      </div>

      {/* Upcoming interviews: each row opens that interview's detail page */}
      <section className="rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-4 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-6">
        <div className="mb-5 flex items-baseline justify-between gap-3">
          <h2 className="font-(family-name:--font-pixel) text-2xl font-medium tracking-tight">Upcoming Interviews</h2>
          <span className="font-(family-name:--font-pixel) text-sm text-neutral-500">{upcoming.length} scheduled</span>
        </div>
        <ul className="divide-y divide-[rgba(15,0,0,0.08)] overflow-hidden rounded-xl border border-[rgba(15,0,0,0.12)]">
          {upcoming.map((i) => (
            <li key={i.id}>
              <Link
                href={`/interviewer/interviews/${i.id}`}
                className="flex items-center justify-between px-4 py-3.5 transition-colors hover:bg-neutral-50"
              >
                <span>{i.name}</span>
                <span className="font-(family-name:--font-pixel) text-sm text-neutral-500">{new Date(i.time).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
