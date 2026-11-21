// Interviews tab: the signed-in interviewer's own interviews, earliest first.
import InterviewCard from "../../components/InterviewCard";
import { getCurrentInterviewer, getInterviewsForInterviewer } from "@/lib/interviews";

export default async function InterviewsPage() {
  const interviewer = await getCurrentInterviewer();
  const interviews = await getInterviewsForInterviewer(interviewer.id); // filtered to this interviewer + sorted

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; interviewer /&gt;</p>
          <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">Interviews</h1>
        </div>
        <span className="font-(family-name:--font-pixel) text-sm text-neutral-500">
          {interviews.length} scheduled
        </span>
      </div>

      {interviews.length === 0 ? (
        <p className="text-neutral-900/60">No interviews scheduled.</p>
      ) : (
        // 1 / 2 / 3 columns depending on screen width; each card links to its detail page
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {interviews.map((i) => (
            <InterviewCard key={i.id} interview={i} />
          ))}
        </div>
      )}
    </main>
  );
}
