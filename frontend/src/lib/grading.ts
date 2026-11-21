// Shared grading data used by the Written Applications page (where interviewers grade)
// and the Applicants page (where the board sees the scores).
// Everything here is mock/demo data until the backend exists.

export type Criterion = { id: string; label: string; description: string; max: number };
export type Applicant = {
  id: string;
  name: string;
  initials: string;
  college: string;
  year: string;
  submitted: string;
  status: "Not started" | "In progress" | "Graded";
  answers: { question: string; response: string }[];
};
export type Grade = {
  scores: Record<string, number>;
  responseScores: Record<number, number>;
  responseNotes: Record<number, string>;
  notes: string;
  recommendation: "Strong yes" | "Yes" | "Maybe" | "No" | "";
  completed: boolean;
};

// Grades are saved in the browser under this key (one object: applicant id -> Grade).
export const GRADES_STORAGE_KEY = "riceapps-application-grades-v2";

export const rubric: Criterion[] = [
  { id: "motivation", label: "Interest & motivation", description: "Why they want to join RiceApps and what they hope to contribute", max: 5 },
  { id: "technical", label: "Technical experience & potential", description: "Relevant programming or design experience, problem-solving, and willingness to learn", max: 5 },
  { id: "collaboration", label: "Collaboration & communication", description: "Ability to work on a team, communicate ideas, and accept feedback", max: 5 },
  { id: "impact", label: "Initiative & project impact", description: "Ownership, creativity, and interest in building useful products for the Rice community", max: 5 },
];

export const applicants: Applicant[] = [
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

export const emptyGrade = (): Grade => ({ scores: {}, responseScores: {}, responseNotes: {}, notes: "", recommendation: "", completed: false });
export const scoreFor = (grade: Grade) => Object.values(grade.scores).reduce((sum, score) => sum + score, 0);
export const responseScoreFor = (grade: Grade) => Object.values(grade.responseScores ?? {}).reduce((sum, score) => sum + score, 0);

// Written response grade: each answer is scored 1-3, so the max is 3 per question.
export const writtenMaxFor = (applicant: Applicant) => applicant.answers.length * 3;
export const writtenFullyScored = (applicant: Applicant, grade: Grade | undefined) =>
  applicant.answers.every((_, index) => grade?.responseScores?.[index] !== undefined);
