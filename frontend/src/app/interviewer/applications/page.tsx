"use client";

import { useEffect, useMemo, useState } from "react";

type Criterion = { id: string; label: string; description: string; max: number };
type Applicant = {
  id: string;
  name: string;
  initials: string;
  college: string;
  year: string;
  submitted: string;
  status: "Not started" | "In progress" | "Graded";
  answers: { question: string; response: string }[];
};
type Grade = {
  scores: Record<string, number>;
  responseScores: Record<number, number>;
  responseNotes: Record<number, string>;
  notes: string;
  recommendation: "Strong yes" | "Yes" | "Maybe" | "No" | "";
  completed: boolean;
};

const rubric: Criterion[] = [
  { id: "motivation", label: "Interest & motivation", description: "Why they want to join RiceApps and what they hope to contribute", max: 5 },
  { id: "technical", label: "Technical experience & potential", description: "Relevant programming or design experience, problem-solving, and willingness to learn", max: 5 },
  { id: "collaboration", label: "Collaboration & communication", description: "Ability to work on a team, communicate ideas, and accept feedback", max: 5 },
  { id: "impact", label: "Initiative & project impact", description: "Ownership, creativity, and interest in building useful products for the Rice community", max: 5 },
];

const applicants: Applicant[] = [
  { id: "APP-1042", name: "Jordan Lee", initials: "JL", college: "Duncan College", year: "Sophomore", submitted: "Nov 18, 2026", status: "Not started", answers: [
    { question: "Why do you want to join RiceApps?", response: "I want to build technology that directly helps students at Rice. RiceApps seems like the perfect place to combine my interest in software engineering with real-world product development and a collaborative team environment." },
    { question: "Tell us about a technical or creative project you've worked on.", response: "I built a course-planning web app with React and a small Python API. I learned how to structure components, handle user input, and iterate based on feedback from classmates who tested it." },
    { question: "Describe a time you collaborated with others or solved a difficult problem.", response: "For a class project, our team disagreed about which features to prioritize. I proposed a small MVP, organized tasks, and helped us release a working version before adding improvements." },
  ] },
  { id: "APP-1043", name: "Taylor Morgan", initials: "TM", college: "Martel College", year: "Junior", submitted: "Nov 18, 2026", status: "Not started", answers: [
    { question: "Why do you want to join RiceApps?", response: "I enjoy designing thoughtful digital experiences and would love to work with developers to make campus tools easier to use." },
    { question: "Tell us about a technical or creative project you've worked on.", response: "I designed a mobile prototype in Figma, interviewed potential users, and revised the layouts based on usability feedback." },
    { question: "Describe a time you collaborated with others or solved a difficult problem.", response: "I worked with a student organization to redesign its website, balancing stakeholder requests with accessibility and usability." },
  ] },
  { id: "APP-1044", name: "Alex Rivera", initials: "AR", college: "Brown College", year: "Sophomore", submitted: "Nov 19, 2026", status: "Not started", answers: [
    { question: "Why do you want to join RiceApps?", response: "I'm excited to learn from other builders while working on projects that have a meaningful impact on student life." },
    { question: "Tell us about a technical or creative project you've worked on.", response: "I created a Discord bot that helps my student group coordinate events, using JavaScript and a database to keep track of responses." },
    { question: "Describe a time you collaborated with others or solved a difficult problem.", response: "When our bot stopped working after an API change, I worked with a friend to debug the issue and add tests to prevent regressions." },
  ] },
  { id: "APP-1045", name: "Casey Patel", initials: "CP", college: "Wiess College", year: "Junior", submitted: "Nov 19, 2026", status: "Not started", answers: [
    { question: "Why do you want to join RiceApps?", response: "I'd like to contribute to products students actually use and strengthen my skills in full-stack development." },
    { question: "Tell us about a technical or creative project you've worked on.", response: "I built a small scheduling tool with Next.js and PostgreSQL, focusing on authentication and clear error messages." },
    { question: "Describe a time you collaborated with others or solved a difficult problem.", response: "I coordinated a hackathon team by splitting work into small tasks and checking in regularly as we combined our features." },
  ] },
  { id: "APP-1046", name: "Sam Chen", initials: "SC", college: "Sid Richardson College", year: "Sophomore", submitted: "Nov 20, 2026", status: "Not started", answers: [
    { question: "Why do you want to join RiceApps?", response: "RiceApps would let me explore software development with a community of people who enjoy learning and shipping useful things." },
    { question: "Tell us about a technical or creative project you've worked on.", response: "I made a personal budgeting app in Python and have been learning React to improve its interface." },
    { question: "Describe a time you collaborated with others or solved a difficult problem.", response: "In a programming assignment, I helped my group isolate a tricky bug by reproducing it with simpler test cases." },
  ] },
];

const emptyGrade = (): Grade => ({ scores: {}, responseScores: {}, responseNotes: {}, notes: "", recommendation: "", completed: false });
const scoreFor = (grade: Grade) => Object.values(grade.scores).reduce((sum, score) => sum + score, 0);
const responseScoreFor = (grade: Grade) => Object.values(grade.responseScores ?? {}).reduce((sum, score) => sum + score, 0);
const responsesFullyScored = (applicant: Applicant, grade: Grade) => applicant.answers.every((_, index) => grade.responseScores?.[index] !== undefined);
const fullyScored = (grade: Grade) => rubric.every((item) => grade.scores[item.id] !== undefined);
// Higher rubric scores receive a progressively more positive visual treatment.
const scoreTone = (score: number | undefined) => {
  if (score === undefined) return "border-neutral-200 bg-neutral-50 text-neutral-500";
  if (score >= 4) return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (score === 3) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-rose-200 bg-rose-50 text-rose-800";
};
const responseScoreTone = (score: number | undefined) => {
  if (score === undefined) return "border-neutral-200 bg-neutral-50 text-neutral-500";
  if (score === 3) return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (score === 2) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-rose-200 bg-rose-50 text-rose-800";
};

export default function ApplicationsPage() {
  const [selectedId, setSelectedId] = useState(applicants[0].id);
  const [grades, setGrades] = useState<Record<string, Grade>>({});
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All applications");
  const [activeTab, setActiveTab] = useState<"application" | "evaluation">("application");
  const [saveMessage, setSaveMessage] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [notice, setNotice] = useState("");

  // Persist grades to v2 key.
  const persistGrades = (nextGrades: Record<string, Grade>) => {
    try {
      window.localStorage.setItem("riceapps-application-grades-v2", JSON.stringify(nextGrades));
      return true;
    } catch {
      return false;
    }
  };

  // Migration: try to load v2; if not found, migrate v1 (5-point written), convert, save to v2, and load it.
  useEffect(() => {
    try {
      const savedV2 = window.localStorage.getItem("riceapps-application-grades-v2");
      if (savedV2) {
        setGrades(JSON.parse(savedV2));
        setLoaded(true);
        return;
      }
      // Try v1
      const savedV1 = window.localStorage.getItem("riceapps-application-grades-v1");
      if (savedV1) {
        const oldGrades = JSON.parse(savedV1);
        // Convert written response grades from 5-point to 3-point.
        const migrated: Record<string, Grade> = {};
        for (const [id, grade] of Object.entries(oldGrades)) {
          migrated[id] = {
            ...grade,
            responseScores: Object.fromEntries(
              Object.entries(grade.responseScores ?? {}).map(([k, v]) => [
                k,
                Math.max(1, Math.min(3, Math.round((v * 3) / 5)))
              ])
            ),
            completed: false, // Mark migrated as not completed.
          };
        }
        window.localStorage.setItem("riceapps-application-grades-v2", JSON.stringify(migrated));
        setGrades(migrated);
      }
    } catch { /* Ignore unavailable or invalid local storage. */ }
    setLoaded(true);
  }, []);

  const updateGrade = (id: string, changes: Partial<Grade>) => {
    setGrades((current) => {
      const updated = {
        ...current,
        [id]: { ...(current[id] ?? emptyGrade()), ...changes, completed: false },
      };
      persistGrades(updated);
      return updated;
    });
    setSaveMessage("Draft saved in this browser");
    setNotice("");
  };
  const saveDraft = () => {
    if (persistGrades(grades)) {
      setSaveMessage(`Draft saved for ${selected.name}`);
      setNotice("");
    } else {
      setNotice("Could not save to browser storage. Please check your browser settings.");
    }
  };

  const clearEvaluation = () => {
    if (!window.confirm(`Clear all scores, notes, and the recommendation for ${selected.name}?`)) return;
    const next = { ...grades, [selected.id]: emptyGrade() };
    setGrades(next);
    persistGrades(next);
    setSaveMessage(`Evaluation reset for ${selected.name}`);
    setNotice("");
  };

  const exportEvaluations = () => {
    const output = applicants.map((applicant) => {
      const grade = grades[applicant.id] ?? emptyGrade();
      return {
        applicationId: applicant.id,
        applicant: applicant.name,
        college: applicant.college,
        status: statusOf(applicant),
        scores: grade.scores,
        responseScores: grade.responseScores ?? {},
        responseNotes: grade.responseNotes ?? {},
        writtenResponseTotal: responseScoreFor(grade),
        combinedTotal: scoreFor(grade) + responseScoreFor(grade),
        combinedMaximum: rubric.reduce((sum, item) => sum + item.max, 0) + applicant.answers.length * 3,
        totalScore: scoreFor(grade),
        recommendation: grade.recommendation,
        notes: grade.notes,
      };
    });
    const blob = new Blob([JSON.stringify(output, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "riceapps-applicant-evaluations.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setNotice("Evaluations exported as JSON.");
  };


  const selected = applicants.find((item) => item.id === selectedId) ?? applicants[0];
  const currentGrade = grades[selected.id] ?? emptyGrade();
  const statusOf = (applicant: Applicant) => {
    const grade = grades[applicant.id];
    if (grade?.completed) return "Graded";
    if (
      grade &&
      (
        Object.keys(grade.scores).length > 0 ||
        Object.keys(grade.responseScores ?? {}).length > 0 ||
        Object.values(grade.responseNotes ?? {}).some(Boolean) ||
        grade.notes ||
        grade.recommendation
      )
    ) return "In progress";
    return applicant.status;
  };
  const gradedCount = applicants.filter((applicant) => statusOf(applicant) === "Graded").length;
  const inProgressCount = applicants.filter((applicant) => statusOf(applicant) === "In progress").length;
  const filteredApplicants = useMemo(() => applicants.filter((item) => {
    const matchesQuery = `${item.name} ${item.college} ${item.id}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (filter === "All applications" || statusOf(item) === filter);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [query, filter, grades]);

  const submitEvaluation = () => {
    if (!fullyScored(currentGrade) || !responsesFullyScored(selected, currentGrade) || !currentGrade.recommendation) {
      setNotice("Please score every written response, score all four rubric criteria, and choose a recommendation before completing this evaluation.");
      setActiveTab("evaluation");
      return;
    }
    const updated = { ...grades, [selected.id]: { ...currentGrade, completed: true } };
    setGrades(updated);
    if (persistGrades(updated)) {
      setSaveMessage(`Evaluation completed for ${selected.name}`);
      setNotice("");
    } else {
      setNotice("Could not save the completed evaluation. Browser storage may be disabled.");
    }
  };

  const nextApplicant = () => {
    const index = applicants.findIndex((item) => item.id === selected.id);
    setSelectedId(applicants[(index + 1) % applicants.length].id);
    setActiveTab("application");
    setSaveMessage("");
    setNotice("");
  };

  return (
    <main className="mx-auto max-w-[1440px] px-5 pb-16 pt-8 text-neutral-900 sm:px-8">
      <div className="mb-9 flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-3 font-(family-name:--font-pixel) text-sm text-neutral-500">&lt; riceapps / applications &gt;</p>
          <h1 className="font-(family-name:--font-pixel) text-4xl font-medium tracking-tight sm:text-5xl">Written Applications</h1>
          <p className="mt-3 text-sm text-neutral-500">Review RiceApps applications, score applicants, and track your evaluations.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-full border border-neutral-200 bg-white px-4 py-2 text-xs font-medium text-neutral-500">2026–27 RiceApps Recruitment <span className="ml-2 text-neutral-900">● Active</span></div>
          <button type="button" onClick={exportEvaluations} className="rounded-xl border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold transition hover:bg-neutral-50">Export evaluations ↓</button>
        </div>
      </div>

      <section className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Total applications", value: applicants.length, detail: "Assigned to you" },
          { label: "Reviewed", value: gradedCount, detail: "Evaluations complete" },
          { label: "In progress", value: inProgressCount, detail: "Draft evaluations" },
          { label: "Remaining", value: applicants.length - gradedCount, detail: "Awaiting review" },
        ].map((stat) => <div key={stat.label} className="rounded-2xl border border-neutral-200 bg-white px-5 py-5">
          <p className="text-xs font-medium text-neutral-500">{stat.label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight">{stat.value.toString().padStart(2, "0")}</p>
          <p className="mt-1 text-xs text-neutral-400">{stat.detail}</p>
        </div>)}
      </section>

      <div className="grid min-h-[690px] gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
          <div className="border-b border-neutral-100 px-5 py-5">
            <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Applicants</h2><span className="text-xs text-neutral-400">{filteredApplicants.length} shown</span></div>
            <label className="block"><span className="sr-only">Search applicants</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name or college..." className="w-full rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2.5 text-sm outline-none transition focus:border-neutral-500" /></label>
            <label className="mt-3 block"><span className="sr-only">Filter applications by status</span><select value={filter} onChange={(event) => setFilter(event.target.value)} className="w-full rounded-xl border border-neutral-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-neutral-500"><option>All applications</option><option>Not started</option><option>In progress</option><option>Graded</option></select></label>
          </div>
          <div className="max-h-[740px] overflow-y-auto p-2" aria-label="Applicant list">
            {filteredApplicants.length === 0 && <p className="px-3 py-8 text-center text-sm text-neutral-400">No applicants found.</p>}
            {filteredApplicants.map((applicant) => {
              const status = statusOf(applicant);
              const active = applicant.id === selected.id;
              return <button key={applicant.id} type="button" onClick={() => { setSelectedId(applicant.id); setActiveTab("application"); setSaveMessage(""); setNotice(""); }} className={`mb-1 flex w-full items-start gap-3 rounded-xl p-3 text-left transition ${active ? "bg-neutral-900 text-white" : "hover:bg-neutral-50"}`}>
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${active ? "bg-white/15 text-white" : "bg-neutral-100 text-neutral-600"}`}>{applicant.initials}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{applicant.name}</span><span className={`mt-0.5 block truncate text-xs ${active ? "text-neutral-300" : "text-neutral-500"}`}>{applicant.college}</span><span className={`mt-2 inline-flex rounded-full px-2 py-1 text-[10px] font-medium ${active ? "bg-white/15 text-white" : status === "Graded" ? "bg-emerald-50 text-emerald-700" : status === "In progress" ? "bg-amber-50 text-amber-700" : "bg-neutral-100 text-neutral-500"}`}>{status}</span></span>
                <span className={`mt-3 text-lg ${active ? "text-neutral-300" : "text-neutral-300"}`}>›</span>
              </button>;
            })}
          </div>
        </aside>

        <section className="min-w-0 overflow-hidden rounded-2xl border border-neutral-200 bg-white">
          <div className="border-b border-neutral-100 px-5 py-6 sm:px-7">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div><div className="mb-2 flex flex-wrap items-center gap-2"><span className="text-xs font-medium tracking-wide text-neutral-400">APPLICATION {selected.id}</span><span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[11px] font-medium text-neutral-600">{statusOf(selected)}</span></div><h2 className="text-2xl font-semibold tracking-tight">{selected.name}</h2><p className="mt-1 text-sm text-neutral-500">{selected.college} <span className="mx-2 text-neutral-300">·</span> {selected.year} <span className="mx-2 text-neutral-300">·</span> Submitted {selected.submitted}</p></div>
              <button type="button" onClick={nextApplicant} className="rounded-xl border border-neutral-200 px-4 py-2.5 text-sm font-medium transition hover:bg-neutral-50">Next applicant <span aria-hidden="true">→</span></button>
            </div>
          </div>
          <div className="flex gap-7 border-b border-neutral-100 px-5 sm:px-7" role="tablist" aria-label="Application review sections">
            <button type="button" role="tab" aria-selected={activeTab === "application"} onClick={() => setActiveTab("application")} className={`border-b-2 py-4 text-sm font-medium ${activeTab === "application" ? "border-neutral-900 text-neutral-900" : "border-transparent text-neutral-400 hover:text-neutral-700"}`}>Application responses</button>
            <button type="button" role="tab" aria-selected={activeTab === "evaluation"} onClick={() => setActiveTab("evaluation")} className={`border-b-2 py-4 text-sm font-medium ${activeTab === "evaluation" ? "border-neutral-900 text-neutral-900" : "border-transparent text-neutral-400 hover:text-neutral-700"}`}>Grade & evaluate <span className="ml-1 text-neutral-400">({Object.keys(currentGrade.scores).length}/{rubric.length})</span></button>
          </div>

          {activeTab === "application" ? <div className="space-y-8 px-5 py-7 sm:px-7">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Written responses</h3><span className="text-xs text-neutral-400">{selected.answers.length} questions</span></div>
            <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 ${Object.keys(currentGrade.responseScores ?? {}).length === 0 ? "border-neutral-200 bg-neutral-50" : responseScoreTone(Math.round(responseScoreFor(currentGrade) / Object.keys(currentGrade.responseScores ?? {}).length))}`}>
              <div><p className="text-xs font-medium">Written responses total</p><p className="mt-1 text-2xl font-semibold">{responseScoreFor(currentGrade)} <span className="text-sm font-normal opacity-70">/ {selected.answers.length * 3}</span></p></div>
              <p className="text-xs">{Object.keys(currentGrade.responseScores ?? {}).length} of {selected.answers.length} scored</p>
            </div>
            {selected.answers.map((answer, index) => (
              <article key={index} className={`rounded-xl border p-5 transition-colors ${responseScoreTone(currentGrade.responseScores?.[index])}`}>
                <div className="mb-3 flex items-start gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/80 text-xs font-semibold text-neutral-600">{String(index + 1).padStart(2, "0")}</span>
                  <h4 className="pt-1 text-sm font-semibold leading-relaxed">{answer.question}</h4>
                </div>
                <p className="mb-6 pl-10 text-sm leading-7 text-neutral-700">{answer.response}</p>
                <div className="border-t border-current/10 pt-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <label className="text-sm font-semibold">Written response score</label>
                    <span className="text-sm font-semibold">{currentGrade.responseScores?.[index] ?? "—"} / 3</span>
                  </div>
                  <div className="mb-4 grid grid-cols-3 gap-2">
                    {[1, 2, 3].map((number) => (
                      <button
                        key={number}
                        type="button"
                        aria-label={`Written response ${index + 1}: ${number} out of 3`}
                        aria-pressed={currentGrade.responseScores?.[index] === number}
                        onClick={() => updateGrade(selected.id, { responseScores: { ...(currentGrade.responseScores ?? {}), [index]: number } })}
                        className={`rounded-lg border py-2.5 text-sm font-semibold transition ${currentGrade.responseScores?.[index] === number ? "border-current bg-white/80 shadow-sm ring-1 ring-current" : "border-neutral-200 bg-white hover:border-neutral-500"}`}
                      >{number}</button>
                    ))}
                  </div>
                  <label htmlFor={`response-notes-${index}`} className="mb-2 block text-xs font-semibold">Response feedback <span className="font-normal opacity-70">(optional)</span></label>
                  <textarea
                    id={`response-notes-${index}`}
                    rows={2}
                    value={currentGrade.responseNotes?.[index] ?? ""}
                    onChange={(event) => updateGrade(selected.id, { responseNotes: { ...(currentGrade.responseNotes ?? {}), [index]: event.target.value } })}
                    placeholder="What stood out in this answer?"
                    className="w-full resize-y rounded-lg border border-neutral-200 bg-white p-3 text-sm text-neutral-900 outline-none focus:border-neutral-500"
                  />
                </div>
              </article>
            ))}
            {statusOf(selected) !== "Not started" && <p className="rounded-xl bg-neutral-50 px-4 py-3 text-sm text-neutral-600">{statusOf(selected) === "Graded" ? `Evaluation complete — ${scoreFor(currentGrade) + responseScoreFor(currentGrade)}/${rubric.reduce((sum, item) => sum + item.max, 0) + selected.answers.length * 3} combined points. You can revisit the grade at any time.` : "You have an evaluation draft in progress for this applicant."}</p>}
            {saveMessage && <p role="status" className="text-xs text-neutral-500">{saveMessage}</p>}
            <div className="flex justify-end"><button type="button" onClick={() => setActiveTab("evaluation")} className="rounded-xl bg-neutral-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-neutral-700">Continue to overall evaluation <span aria-hidden="true">→</span></button></div>
          </div> : <div className="space-y-7 px-5 py-7 sm:px-7">
            <div className={`flex flex-wrap items-center justify-between gap-4 rounded-xl border p-5 transition-colors ${Object.keys(currentGrade.scores).length === 0 ? "border-neutral-200 bg-neutral-50" : scoreTone(scoreFor(currentGrade) / Object.keys(currentGrade.scores).length)}`}><div><p className="text-xs font-medium text-neutral-500">Overall rubric score</p><p className="mt-1 text-3xl font-semibold">{scoreFor(currentGrade)} <span className="text-base font-normal text-neutral-400">/ {rubric.reduce((sum, item) => sum + item.max, 0)}</span></p></div><div className="text-xs text-neutral-500">{Object.keys(currentGrade.scores).length} of {rubric.length} criteria scored</div></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4"><p className="text-xs text-neutral-500">Written response scores</p><p className="mt-1 text-xl font-semibold">{responseScoreFor(currentGrade)} / {selected.answers.length * 3}</p><p className="mt-1 text-xs text-neutral-500">{Object.keys(currentGrade.responseScores ?? {}).length} of {selected.answers.length} responses scored</p></div>
              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4"><p className="text-xs text-neutral-500">Combined evaluation total</p><p className="mt-1 text-xl font-semibold">{scoreFor(currentGrade) + responseScoreFor(currentGrade)} / {rubric.reduce((sum, item) => sum + item.max, 0) + selected.answers.length * 3}</p><p className="mt-1 text-xs text-neutral-500">Rubric + written responses</p></div>
            </div>
            <div><h3 className="text-sm font-semibold">Evaluation rubric</h3><p className="mt-1 text-xs text-neutral-500">Select a score from 1 (limited evidence) to 5 (exceptional evidence) for each criterion.</p></div>
            <div className="space-y-6">{rubric.map((criterion) => <div key={criterion.id} className={`rounded-xl border p-4 transition-colors ${scoreTone(currentGrade.scores[criterion.id])}`}><div className="mb-4 flex flex-wrap items-start justify-between gap-2"><div><h4 className="text-sm font-semibold">{criterion.label}</h4><p className="mt-1 text-xs leading-5 text-neutral-500">{criterion.description}</p></div><span className="text-sm font-semibold text-neutral-500">{currentGrade.scores[criterion.id] ?? "—"} / {criterion.max}</span></div><div className="grid grid-cols-5 gap-2">{Array.from({ length: criterion.max }, (_, index) => index + 1).map((number) => <button key={number} type="button" aria-label={`${criterion.label}: ${number} out of ${criterion.max}`} aria-pressed={currentGrade.scores[criterion.id] === number} onClick={() => updateGrade(selected.id, { scores: { ...currentGrade.scores, [criterion.id]: number } })} className={`rounded-lg border py-2.5 text-sm font-semibold transition ${currentGrade.scores[criterion.id] === number ? "border-current bg-white/80 shadow-sm ring-1 ring-current" : "border-neutral-200 hover:border-neutral-500"}`}>{number}</button>)}</div></div>)}</div>
            <div><label htmlFor="review-notes" className="text-sm font-semibold">Reviewer notes</label><p className="mb-3 mt-1 text-xs text-neutral-500">Capture technical strengths, collaboration examples, areas for growth, and points to discuss with the RiceApps team.</p><textarea id="review-notes" value={currentGrade.notes} onChange={(event) => updateGrade(selected.id, { notes: event.target.value })} placeholder="Add your evaluation notes here..." rows={5} className="w-full resize-y rounded-xl border border-neutral-200 p-4 text-sm leading-6 outline-none focus:border-neutral-500" /></div>
            <fieldset><legend className="text-sm font-semibold">Overall recommendation</legend><p className="mb-3 mt-1 text-xs text-neutral-500">Choose your recommendation for this applicant.</p><div className="flex flex-wrap gap-2">{(["Strong yes", "Yes", "Maybe", "No"] as const).map((option) => <button key={option} type="button" aria-pressed={currentGrade.recommendation === option} onClick={() => updateGrade(selected.id, { recommendation: option })} className={`rounded-full border px-4 py-2 text-xs font-semibold transition ${currentGrade.recommendation === option ? "border-neutral-900 bg-neutral-900 text-white" : "border-neutral-200 text-neutral-600 hover:border-neutral-500"}`}>{option}</button>)}</div></fieldset>
            <div className="border-t border-neutral-100 pt-6">
              {notice && <p role="alert" className="mb-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">{notice}</p>}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span role="status" className="text-xs text-neutral-500">{saveMessage || (loaded ? "Changes are saved in this browser" : "Loading drafts...")}</span>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={clearEvaluation} className="rounded-xl border border-rose-200 px-4 py-3 text-sm font-semibold text-rose-700 transition hover:bg-rose-50">Reset</button>
                  <button type="button" onClick={saveDraft} className="rounded-xl border border-neutral-200 px-4 py-3 text-sm font-semibold transition hover:bg-neutral-50">Save draft</button>
                  <button type="button" onClick={submitEvaluation} className="rounded-xl bg-neutral-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-neutral-700">{currentGrade.completed ? "Update evaluation" : "Complete evaluation"} <span aria-hidden="true">✓</span></button>
                </div>
              </div>
            </div>
          </div>}
        </section>
      </div>
      <p className="mt-5 text-xs text-neutral-400">Demo applicants only · Functional search, filtering, scoring, per-response written grading, draft saving, completion, reset, and JSON export. Evaluations are stored locally in your browser; connect a backend before using real applicant data.</p>
    </main>
  );
}