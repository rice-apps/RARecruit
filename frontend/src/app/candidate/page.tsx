import InterviewScheduler from "../components/InterviewScheduler";

export default function CandidateHome() {
  return (
    <main>
      <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; candidate /&gt;</p>
      <h1 className="font-(family-name:--font-pixel) text-5xl font-medium tracking-tight sm:text-6xl">Candidate</h1>

      <InterviewScheduler />
    </main>
  );
}
