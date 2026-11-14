"use client";
import { useState } from "react";

const PX = "font-(family-name:--font-pixel)";

// Google's multi-color "G" mark, per Google's sign-in button branding guidelines
function GoogleIcon() {
  return (
    <svg aria-hidden viewBox="0 0 48 48" className="h-5 w-5">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export default function LoginForm() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signInWithGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      // TODO (when Supabase is wired up): this redirects to Google, then back to the app.
      //   await supabase.auth.signInWithOAuth({
      //     provider: "google",
      //     options: { redirectTo: `${window.location.origin}/auth/callback` },
      //   });
      console.log("Google sign-in clicked (not wired up yet)");
      await new Promise((r) => setTimeout(r, 800));
      setLoading(false);
    } catch {
      setError("Couldn't sign in with Google. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-8 shadow-[0_4px_24px_rgba(0,0,0,0.04)] sm:p-10">
      <p className={`${PX} mb-8 text-center text-xl tracking-tight`}>&lt; RARecruit /&gt;</p>

      <h1 className={`${PX} text-center text-4xl font-medium tracking-tight sm:text-5xl`}>Welcome</h1>
      <p className="mt-1 text-center font-(family-name:--font-serif) text-2xl italic text-neutral-400">
        sign in to continue
      </p>

      <button
        onClick={signInWithGoogle}
        disabled={loading}
        className={`group mt-10 flex h-12 w-full cursor-pointer items-center justify-center gap-3 rounded-[4px] border border-[rgba(15,0,0,0.2)] bg-white ${PX} text-sm text-[#212529]
          shadow-[3px_3px_0_rgba(33,37,41,0.12)] transition-all duration-200
          hover:-translate-x-0.5 hover:-translate-y-0.5 hover:border-[#212529] hover:shadow-[5px_5px_0_rgba(33,37,41,0.2)]
          active:translate-x-0 active:translate-y-0 active:shadow-[1px_1px_0_rgba(33,37,41,0.2)]
          disabled:cursor-default disabled:opacity-60 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:border-[rgba(15,0,0,0.2)] disabled:hover:shadow-[3px_3px_0_rgba(33,37,41,0.12)]`}
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-[#212529]" />
        ) : (
          <GoogleIcon />
        )}
        {loading ? "Redirecting…" : "Continue with Google"}
      </button>

      {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}

      <p className="mt-8 text-center text-sm text-neutral-500">
        Use your <span className="text-neutral-900">Rice</span> Google account.
      </p>
    </div>
  );
}
