import Link from "next/link";
import { Droplet } from "lucide-react";

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-sky-600 text-white shadow-card">
            <Droplet className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="text-lg font-bold tracking-tight text-slate-900">
            Aarogya <span className="text-brand-600">Bindu</span>
          </span>
        </Link>

        <nav
          className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex"
          aria-label="Primary"
        >
          <a href="#tests" className="transition hover:text-brand-700">
            Screening Tests
          </a>
          <a href="#how-it-works" className="transition hover:text-brand-700">
            How It Works
          </a>
        </nav>

        <Link
          href="/screening"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
        >
          Start Screening
        </Link>
      </div>
    </header>
  );
}
