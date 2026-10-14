import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'Math Council - Hội Đồng Toán Học AI',
  description: 'Hệ thống giải toán nâng cao dựa trên mô hình hội đồng AI đa tác nhân',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased">
        <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center space-x-3">
                <Link href="/" className="flex items-center space-x-2.5">
                  <span className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-md shadow-indigo-200">
                    ∑
                  </span>
                  <div>
                    <span className="text-xl font-bold bg-gradient-to-r from-indigo-700 to-indigo-500 bg-clip-text text-transparent">
                      Math Council
                    </span>
                    <span className="block text-[10px] font-medium text-slate-500 -mt-1 tracking-wider uppercase">
                      Hội Đồng Toán Học AI
                    </span>
                  </div>
                </Link>
              </div>

              <nav className="flex items-center space-x-1 sm:space-x-4">
                <Link
                  href="/"
                  className="px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:text-indigo-600 hover:bg-slate-100 transition-colors"
                >
                  Trang chủ
                </Link>
                <Link
                  href="/problems"
                  className="px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:text-indigo-600 hover:bg-slate-100 transition-colors"
                >
                  Kho bài toán
                </Link>
                <Link
                  href="/problems/new"
                  className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-300 transition-all active:scale-[0.98]"
                >
                  + Tạo bài toán mới
                </Link>
              </nav>
            </div>
          </div>
        </header>

        <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        <footer className="bg-white border-t border-slate-200 py-6 mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-center text-xs text-slate-500 gap-2">
            <div>
              © 2026 Math Council (Bước 2 Walking Skeleton). Xây dựng trên Next.js + FastAPI + PostgreSQL.
            </div>
            <div className="flex items-center space-x-2">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
              <span>API Gateway Sẵn Sàng</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
