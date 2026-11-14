import InterviewCard, { Interview } from "../../components/InterviewCard";

const interviews: Interview[] = [
  { id: "1", name: "Jane Doe", time: "2026-11-10T14:00:00", program: "RiceApps", role: "Developer" },
  { id: "2", name: "John Smith", time: "2026-11-11T10:30:00", program: "RiceApps", role: "Product Manager" },
];

export default function InterviewsPage() {
  const sorted = [...interviews].sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()
  );

  return (
    <main className="mx-auto max-w-[1158px] space-y-8 px-6 pb-16 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; interviewer /&gt;</p>
          <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">Interviews</h1>
        </div>
      </div>

      {sorted.length === 0 ? (
        <p className="text-neutral-900/60">No interviews scheduled.</p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((i) => (
            <InterviewCard key={i.id} interview={i} />
          ))}
        </div>
      )}
    </main>
  );
}
