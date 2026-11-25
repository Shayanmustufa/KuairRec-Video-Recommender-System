import './globals.css';
import { Navbar } from '@/components/Navbar';

export const metadata = {
  title: 'KuaiRec Explainable Short-Video Recommender System',
  description: 'Production-ready explainable recommender interface by Abdul Qadir Satti & Syed Shayan Mustufa Rizvi',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-6 mt-12 text-center text-xs text-slate-500 dark:text-slate-400 transition-colors">
          <p>KuaiRec Recommender System • FAST NUCES Information Systems Project</p>
          <p className="mt-1">
            Abdul Qadir Satti (23K-0674, BCS-7B) • Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)
          </p>
        </footer>
      </body>
    </html>
  );
}
