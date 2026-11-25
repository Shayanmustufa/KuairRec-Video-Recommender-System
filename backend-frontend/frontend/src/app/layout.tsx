import './globals.css';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { CatalogEnglishProvider } from '@/components/CatalogEnglish';
import type { CatalogTranslations } from '@/lib/format';

function loadTranslations(): CatalogTranslations {
  try {
    return JSON.parse(readFileSync(join(process.cwd(), 'public/catalog-english.local.json'), 'utf8'));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
}
import { Navbar } from '@/components/Navbar';

export const metadata = {
  title: 'KuaiRec Explainable Recommender',
  description: 'Explainable short-video recommendations on KuaiRec 2.0 — Go API and Next.js demo.',
};

export const viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-indigo-600 focus:px-3 focus:py-2 focus:text-white"
        >
          Skip to content
        </a>
        <Navbar />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
          <CatalogEnglishProvider translations={loadTranslations()}>{children}</CatalogEnglishProvider>
        </main>
        <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          <p>KuaiRec explainable short-video recommender</p>
          <p className="mt-1">Abdul Qadir Satti (23K-0674, BCS-7B) · Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)</p>
        </footer>
      </body>
    </html>
  );
}
