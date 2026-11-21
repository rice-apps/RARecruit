"use client";
// Top nav for interviewer pages. Client Component because the mobile menu needs open/close state.

import Link from "next/link";
import { useState } from "react";

// Nav items, used by both the desktop bar and the mobile dropdown.
const links = [
  { href: "/interviewer", label: "Home" },
  { href: "/interviewer/availability", label: "Availability" },
  { href: "/interviewer/applications", label: "Applications" },
  { href: "/interviewer/candidates", label: "Candidates" },
  { href: "/interviewer/interviews", label: "Interviews" }
];

// Underline that grows in from the left on hover.
const linkClass =
  "relative inline-block cursor-pointer transition-colors hover:text-neutral-900 " +
  "after:absolute after:-bottom-1 after:left-0 after:h-px after:w-full after:origin-left " +
  "after:scale-x-0 after:bg-neutral-900 after:transition-transform after:duration-300 " +
  "after:ease-out hover:after:scale-x-100";

export default function Navbar() {
  const [open, setOpen] = useState(false); // mobile menu open?

  async function handleLogout() {
    // TODO: replace with your auth's logout call, e.g.
    //   NextAuth:  await signOut({ callbackUrl: "/" });
    //   Supabase:  await supabase.auth.signOut();
    //   Own API:   await fetch("/api/logout", { method: "POST" });
    window.location.href = "/auth/login";
  }

  return (
    <header className="fixed inset-x-0 top-3 z-50 px-3 font-(family-name:--font-pixel) sm:top-5 sm:px-6">
      <nav
        className="mx-auto flex max-w-[1158px] items-center justify-between rounded-[36px] border border-[rgba(15,0,0,0.12)] bg-white/95 px-6 py-2.5 backdrop-blur-md sm:px-9"
        style={{ boxShadow: "0px 5px 6.8px rgba(0,0,0,0.04)" }}
      >
        <Link href="/interviewer" className="text-lg tracking-tight text-neutral-900 sm:text-xl">
          &lt; RARecruit /&gt;
        </Link>

        {/* Desktop links (hidden below md) */}
        <ul className="hidden items-center gap-14 text-base text-neutral-900/80 md:flex">
          {links.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className={linkClass}>
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="hidden items-center md:flex">
          <button
            onClick={handleLogout}
            className="inline-flex cursor-pointer items-center rounded-[4px] bg-neutral-900 px-4 py-1.5 text-base leading-loose text-neutral-100 transition-colors hover:bg-neutral-900/85"
          >
            Log out
          </button>
        </div>

        {/* Mobile menu toggle */}
        <button
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-[4px] border border-[rgba(15,0,0,0.12)] md:hidden"
        >
          {/* Hamburger: three lines that turn into an X when open */}
          <span className="relative block h-4 w-4">
            <span className={`absolute left-0 block h-px w-4 bg-neutral-900 transition-all duration-300 ${open ? "top-1/2 rotate-45" : "top-1"}`} />
            <span className={`absolute left-0 top-1/2 block h-px w-4 bg-neutral-900 transition-opacity duration-200 ${open ? "opacity-0" : "opacity-100"}`} />
            <span className={`absolute left-0 block h-px w-4 bg-neutral-900 transition-all duration-300 ${open ? "top-1/2 -rotate-45" : "top-3"}`} />
          </span>
        </button>
      </nav>

      {/* Mobile dropdown */}
      {open && (
        <div className="mx-auto mt-2 max-w-[1158px] rounded-3xl border border-[rgba(15,0,0,0.12)] bg-white/95 p-6 backdrop-blur-md md:hidden">
          <ul className="flex flex-col gap-4 text-base text-neutral-900/80">
            {links.map((l) => (
              <li key={l.href}>
                {/* close the menu after picking a page */}
                <Link href={l.href} onClick={() => setOpen(false)}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <button
            onClick={handleLogout}
            className="mt-6 w-full cursor-pointer rounded-[4px] bg-neutral-900 px-4 py-2 text-neutral-100"
          >
            Log out
          </button>
        </div>
      )}
    </header>
  );
}
