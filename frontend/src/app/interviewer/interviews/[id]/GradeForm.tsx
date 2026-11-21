"use client";
// The score + summary form on the interview detail page.
// "use client" (above) makes this a Client Component: it runs in the browser,
// which it needs to do to keep track of what the interviewer types and handle
// the Save click. The parent page (page.tsx) runs on the server and passes in
// the starting values.

import { useState } from "react";
import { MAX_SCORE } from "@/lib/interviews";

// Shared styling for the number input and the textarea.
const inputClass =
  "w-full rounded-[4px] border border-[rgba(15,0,0,0.2)] bg-white px-3 py-2 text-neutral-900 " +
  "outline-none transition-colors focus:border-[#212529]";

type Props = {
  interviewId: string; // which interview the score is for (needed when saving to the backend)
  initialGrade: number | null; // null = not scored yet
  initialSummary: string; // "" = no summary yet
};

export default function GradeForm({ interviewId, initialGrade, initialSummary }: Props) {
  // Form state. The score is kept as a string because that's what <input> gives
  // back, and it lets the field be empty; it's converted to a number on save.
  const [grade, setGrade] = useState(initialGrade?.toString() ?? "");
  const [summary, setSummary] = useState(initialSummary);
  // Drives the button text and the "Saved" message next to it.
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle");

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    // Stop the browser's default form submit, which would reload the page.
    e.preventDefault();
    setStatus("saving");
    // TODO: send to the backend grading endpoint once it exists, e.g.
    //   await fetch(`${process.env.NEXT_PUBLIC_API_URL}/interviews/${interviewId}/grade`, {
    //     method: "PUT",
    //     headers: { "Content-Type": "application/json" },
    //     body: JSON.stringify({ grade: Number(grade), summary }),
    //   });
    // Until then nothing is persisted; a page refresh resets the form.
    // For now it just logs to the browser console (DevTools → Console) so you can see what would be sent.
    console.log("save grade", { interviewId, grade: Number(grade), summary });
    setStatus("saved");
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Final score. min/max/step/required are checked by the browser before
          handleSubmit runs, so an empty field, a decimal, or a number outside
          0 to MAX_SCORE can't be saved. */}
      <label className="block space-y-2">
        <span className="font-(family-name:--font-pixel) text-sm text-neutral-500">
          Final score (out of {MAX_SCORE})
        </span>
        <input
          type="number"
          min={0}
          max={MAX_SCORE}
          step={1}
          required
          value={grade}
          onChange={(e) => {
            setGrade(e.target.value);
            // Any edit after saving clears the "Saved" message, since there are unsaved changes again.
            setStatus("idle");
          }}
          className={inputClass}
        />
      </label>

      {/* Paragraph-style summary. resize-y lets the interviewer drag it taller. */}
      <label className="block space-y-2">
        <span className="font-(family-name:--font-pixel) text-sm text-neutral-500">Summary</span>
        <textarea
          rows={8}
          required
          value={summary}
          onChange={(e) => {
            setSummary(e.target.value);
            setStatus("idle"); // same as above: editing means there are unsaved changes
          }}
          placeholder="Overall impressions, strengths, concerns..."
          className={`${inputClass} resize-y`}
        />
      </label>

      <div className="flex items-center gap-4">
        {/* Disabled while saving so a double-click doesn't send two saves. */}
        <button
          type="submit"
          disabled={status === "saving"}
          className="inline-flex h-11 items-center rounded-[4px] border border-[#212529] bg-[#212529] px-5 font-(family-name:--font-pixel) text-sm text-white shadow-[3px_3px_0_rgba(33,37,41,0.25)] transition-all duration-200 hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0_rgba(33,37,41,0.25)] disabled:opacity-60"
        >
          {status === "saving" ? "Saving..." : "Save"}
        </button>
        {status === "saved" && <span className="text-sm text-neutral-500">Saved (demo only, not stored yet)</span>}
      </div>
    </form>
  );
}
