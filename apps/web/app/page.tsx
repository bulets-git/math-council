'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchProblems, ProblemSummary } from '@/lib/api';
import MathRenderer from '@/components/MathRenderer';

export default function HomePage() {
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const data = await fetchProblems(0, 6);
        setProblems(data);
      } catch (err: any) {
        setError(err.message || 'Không thể tải danh sách bài toán');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case 'queued':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-amber-500 animate-pulse"></span>
            Đang chờ (queued)
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-blue-500 animate-spin"></span>
            Đang giải quyết
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
            ✓ Hoàn thành
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-800 border border-rose-200">
            ✕ Thất bại
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
            Chưa có Run
          </span>
        );
    }
  };

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-900 via-indigo-800 to-slate-900 text-white p-8 sm:p-12 shadow-xl shadow-indigo-950/10">
        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-medium border border-indigo-500/30">
            <span>🚀 Bước 2: Walking Skeleton Architecture</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
            Math Council <br />
            <span className="text-indigo-400">Hội Đồng Toán Học AI</span>
          </h1>

          <p className="text-base sm:text-lg text-slate-300 leading-relaxed">
            Hệ thống phân tích và giải toán chuyên sâu dựa trên mô hình hội đồng AI đa tác nhân.
            Hỗ trợ nhập đề toán tiếng Việt, biểu diễn công thức LaTeX toán học chuẩn xác, quản lý
            các phiên giải toán (Runs) theo quy trình kiểm thử nghiêm ngặt.
          </p>

          <div className="flex flex-wrap gap-4 pt-2">
            <Link
              href="/problems/new"
              className="px-6 py-3 rounded-xl bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-500/30 hover:bg-indigo-400 transition-all active:scale-[0.98] text-sm sm:text-base flex items-center space-x-2"
            >
              <span>+ Tạo bài toán mới</span>
            </Link>
            <Link
              href="/problems"
              className="px-6 py-3 rounded-xl bg-white/10 text-white font-semibold backdrop-blur-md hover:bg-white/20 transition-all border border-white/15 text-sm sm:text-base"
            >
              Xem tất cả bài toán
            </Link>
          </div>
        </div>

        {/* Decorative background circle */}
        <div className="absolute -right-20 -bottom-20 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>
      </section>

      {/* Feature Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold mb-4">
            fx
          </div>
          <h3 className="font-bold text-slate-800 text-lg mb-2">Công Thức LaTeX Chuẩn Xác</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Tích hợp bộ parser KaTeX hiển thị mượt mà các ký hiệu đại số, hình học, tích phân, ma trận inline và block.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 font-bold mb-4">
            🏛️
          </div>
          <h3 className="font-bold text-slate-800 text-lg mb-2">Hội Đồng Độc Lập</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Mô hình phối hợp các solver AI chuyên môn hóa, phản biện và tổng hợp lời giải tối ưu nhất cho bài toán.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 font-bold mb-4">
            ⚡
          </div>
          <h3 className="font-bold text-slate-800 text-lg mb-2">Quản Lý Lượt Chạy (Runs)</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Theo dõi từng phiên giải toán với trạng thái queued, quản lý ngân sách USD và lịch sử độc lập.
          </p>
        </div>
      </section>

      {/* Recent Problems Section */}
      <section className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Bài toán gần đây</h2>
            <p className="text-sm text-slate-500">Các bài toán vừa được gửi lên hệ thống Math Council</p>
          </div>
          <Link
            href="/problems"
            className="text-sm font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
          >
            Xem tất cả &rarr;
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-56 rounded-2xl bg-slate-200 animate-pulse"></div>
            ))}
          </div>
        ) : error ? (
          <div className="p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
            {error}
          </div>
        ) : problems.length === 0 ? (
          <div className="text-center py-16 px-4 rounded-2xl bg-white border border-dashed border-slate-300">
            <span className="text-4xl block mb-3">📐</span>
            <h3 className="text-base font-semibold text-slate-800">Chưa có bài toán nào</h3>
            <p className="text-sm text-slate-500 mt-1 mb-6">
              Hãy tạo bài toán đầu tiên để khởi tạo phiên giải toán với Math Council.
            </p>
            <Link
              href="/problems/new"
              className="inline-flex items-center px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
            >
              + Tạo bài toán mới ngay
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {problems.map((prob) => (
              <Link
                key={prob.id}
                href={`/problems/${prob.id}`}
                className="group block p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start gap-2 mb-3">
                    <div className="flex flex-wrap gap-1.5">
                      {prob.subject && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-indigo-50 text-indigo-700">
                          {prob.subject}
                        </span>
                      )}
                      {prob.difficulty && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700">
                          {prob.difficulty}
                        </span>
                      )}
                    </div>
                    {getStatusBadge(prob.latest_run_status)}
                  </div>

                  <h3 className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1 mb-2">
                    {prob.title || 'Bài toán không tiêu đề'}
                  </h3>

                  <div className="text-sm text-slate-600 line-clamp-3 overflow-hidden mb-4">
                    <MathRenderer content={prob.statement_original} />
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 text-xs text-slate-400 flex justify-between items-center">
                  <span>{new Date(prob.created_at).toLocaleDateString('vi-VN')}</span>
                  <span className="group-hover:translate-x-1 transition-transform font-medium text-indigo-600">
                    Chi tiết &rarr;
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
