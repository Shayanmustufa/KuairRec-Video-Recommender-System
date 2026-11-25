'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { checkHealth } from '@/lib/api';
import { ThemeToggle } from './ThemeToggle';

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const [health, setHealth] = useState<{ status: string; latency: number }>({ status: 'checking', latency: 0 });

  useEffect(() => {
    const updateHealth = async () => {
      const res = await checkHealth();
      setHealth(res);
    };
    updateHealth();
    const interval = setInterval(updateHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const navLinks = [
    { href: '/', label: 'Feed & Recommendations' },
    { href: '/compare', label: 'Model Comparison' },
    { href: '/metrics', label: 'Evaluation & Ablations' },
    { href: '/system', label: 'System & Manifest' },
  ];

  return (
    <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-50 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-indigo-600 text-white font-black flex items-center justify-center text-lg shadow-sm">
                K
              </span>
              <div>
                <span className="font-extrabold text-slate-900 dark:text-white tracking-tight text-base sm:text-lg block leading-none">
                  KuaiRec <span className="text-indigo-600 dark:text-indigo-400">Recommender</span>
                </span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono">Explainable Short-Video System</span>
              </div>
            </Link>
          </div>

          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-semibold'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            {/* Live API Health indicator */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.status === 'healthy'
                    ? 'bg-emerald-500 animate-pulse'
                    : health.status === 'checking'
                    ? 'bg-amber-400'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-700 dark:text-slate-300 font-medium capitalize">{health.status}</span>
              {health.latency >= 0 && (
                <span className="text-slate-400 dark:text-slate-500 text-[10px]">({health.latency}ms)</span>
              )}
            </div>

            {/* Dark & Light Mode Toggle */}
            <ThemeToggle />

            <div className="hidden lg:block text-right">
              <p className="text-[11px] font-bold text-slate-800 dark:text-slate-200 leading-none">Abdul Qadir Satti (23K-0674)</p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-none mt-0.5">Syed Shayan Mustufa (23K-0924)</p>
            </div>
          </div>
        </div>
      </div>
      {/* Mobile nav */}
      <div className="md:hidden flex overflow-x-auto border-t border-slate-100 dark:border-slate-800 px-4 py-2 gap-2 bg-slate-50 dark:bg-slate-950">
        {navLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`whitespace-nowrap px-3 py-1 text-xs rounded-md ${
              pathname === link.href
                ? 'bg-indigo-600 text-white font-medium'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </header>
  );
};
