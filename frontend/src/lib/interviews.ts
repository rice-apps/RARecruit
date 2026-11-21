// Interview data for the interviewer pages.
// Everything here is mock data. Once auth and the backend are wired up, swap
// getCurrentInterviewer() for the signed-in user and the two get* functions
// for calls to the FastAPI grading/scheduling endpoints. Pages only use these
// functions, so they won't need to change.

export type Interviewer = {
  id: string;
  name: string;
};

export type Interview = {
  id: string;
  interviewerId: string;
  name: string; // candidate name
  time: string; // ISO string, e.g. "2026-11-18T14:30:00"
  program: string;
  role: string;
  gradingDocUrl: string; // Google Doc with the grading template for this interview
  grade: number | null;
  summary: string;
};

// Final interview scores are out of this many points.
export const MAX_SCORE = 30;

// Shared grading template. Swap for a per-interview copy later if each interview gets its own doc.
const GRADING_TEMPLATE_URL =
  "https://docs.google.com/document/d/1gr1PcmfGwx87xqov1jLzSUXxaJ8MdE_UWs_cUNl1gck/edit?tab=t.0";

const interviewers: Interviewer[] = [
  { id: "mac", name: "Mac Ajwani" },
  { id: "alex", name: "Alex Chen" },
];

const interviews: Interview[] = [
  {
    id: "1",
    interviewerId: "mac",
    name: "Jane Doe",
    time: "2026-11-10T14:00:00",
    program: "RiceApps",
    role: "Developer",
    gradingDocUrl: GRADING_TEMPLATE_URL,
    grade: null,
    summary: "",
  },
  {
    id: "2",
    interviewerId: "mac",
    name: "John Smith",
    time: "2026-11-11T10:30:00",
    program: "RiceApps",
    role: "Product Manager",
    gradingDocUrl: GRADING_TEMPLATE_URL,
    grade: null,
    summary: "",
  },
  {
    id: "3",
    interviewerId: "mac",
    name: "Priya Patel",
    time: "2026-11-09T16:00:00",
    program: "RiceApps",
    role: "Designer",
    gradingDocUrl: GRADING_TEMPLATE_URL,
    grade: null,
    summary: "",
  }
];

// TODO: replace with the signed-in user once Supabase auth is set up.
export async function getCurrentInterviewer(): Promise<Interviewer> {
  return interviewers[0];
}

// The interviewer's own interviews, earliest first.
export async function getInterviewsForInterviewer(interviewerId: string): Promise<Interview[]> {
  return interviews
    .filter((i) => i.interviewerId === interviewerId)
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
}

// Returns the interview only if it belongs to this interviewer.
export async function getInterview(id: string, interviewerId: string): Promise<Interview | null> {
  return interviews.find((i) => i.id === id && i.interviewerId === interviewerId) ?? null;
}

// Turns a normal Google Docs link into one that can go in an iframe.
export function toEmbedUrl(docUrl: string): string {
  return docUrl.replace(/\/(edit|view)([?#].*)?$/, "/preview");
}
