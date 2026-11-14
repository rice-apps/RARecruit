import Navbar from "../components/Navbar";

// Fonts and the dot-grid background come from the root layout.
export default function InterviewerLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      {/* top padding leaves room for the fixed navbar */}
      <div className="pt-28">{children}</div>
    </>
  );
}
