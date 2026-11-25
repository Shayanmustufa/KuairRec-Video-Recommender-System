'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { checkHealth } from '@/lib/api';
import { ThemeToggle } from './ThemeToggle';

const LINKS = [
  { href: '/', label: 'Recommendations' },
  { href: '/compare', label: 'Compare' },
  { href: '/metrics', label: 'Metrics' },
  { href: '/system', label: 'System' },
];

const DOT: Record<string, string> = {
  healthy: 'bg-emerald-500',
  checking: 'bg-amber-400',
  degraded: 'bg-amber-500',
  unreachable: 'bg-rose-500',
};

export function Navbar() {
  const pathname = usePathname();
  const [health, setHealth] = useState<{ status: string; latency: number }>({ status: 'checking', latency: -1 });

  useEffect(() => {
    let active = true;
    const update = () => checkHealth().then((h) => active && setHealth(h));
    update();
    const id = setInterval(update, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const linkClass = (href: string) =>
    pathname === href
      ? 'bg-indigo-50 font-semibold text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-200'
      : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white';

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-lg font-black text-white"
          >
            K
          </span>
          <span className="text-base font-extrabold leading-none tracking-tight">KuaiRec Recommender</span>
        </Link>
        <nav aria-label="Main" className="hidden md:block">
          <ul className="flex gap-1">
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  aria-current={pathname === link.href ? 'page' : undefined}
                  className={`rounded-lg px-3 py-2 text-sm ${linkClass(link.href)}`}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3">
          <p
            role="status"
            aria-live="polite"
            className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-xs dark:border-slate-700 dark:bg-slate-800"
          >
            <span aria-hidden="true" className={`h-2 w-2 rounded-full ${DOT[health.status] ?? DOT.unreachable}`} />
            <span>API {health.status}</span>
            {health.latency >= 0 && <span className="text-slate-500">({health.latency} ms)</span>}
          </p>
          <ThemeToggle />
        </div>
      </div>
      <nav
        aria-label="Main (mobile)"
        className="flex gap-2 overflow-x-auto border-t border-slate-100 bg-slate-50 px-4 py-2 md:hidden dark:border-slate-800 dark:bg-slate-950"
      >
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            aria-current={pathname === link.href ? 'page' : undefined}
            className={`whitespace-nowrap rounded-md px-3 py-1 text-xs ${linkClass(link.href)}`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
