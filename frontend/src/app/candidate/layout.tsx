export default function CandidateLayout({ children }: { children: React.ReactNode }) {
  // same content width as the navbar / interviewer pages
  return <div className="mx-auto max-w-[1158px] px-6 py-12">{children}</div>;
}
