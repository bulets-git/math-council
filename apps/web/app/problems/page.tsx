'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchProblems, ProblemSummary } from '@/lib/api';
import MathRenderer from '@/components/MathRenderer';

export default function ProblemsListPage() {
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('all');

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const data = await fetchProblems(0, 100);
        setProblems(data);
      } catch (err: any) {
        setError(err.message || 'Không thể tải danh sách bài toán');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const subjects = ['all', 'Đại số', 'Số học', 'Hình học', 'Tổ hợp', 'Bất đẳng thức'];

  const filteredProblems = problems.filter((prob) => {
    const matchesSearch =
      (prob.title && prob.title.toLowerCase().includes(searchTerm.toLowerCase())) ||
      prob.statement_original.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSubject =
      selectedSubject === 'all' ||
      (prob.subject && prob.subject.toLowerCase() === selectedSubject.toLowerCase());
    return matchesSearch && matchesSubject;
  });

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case 'queued':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
            <span className="w-1.5 h-1.5 mr-1 rounded-full bg-amber-500 animate-pulse"></span>
            Queued
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
            Hoàn thành
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
            Chưa có Run
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Kho bài toán</h1>
          <p className="text-sm text-slate-500 mt-1">
            Tổng cộng {problems.length} bài toán đã lưu trữ trên hệ thống Math Council
          </p>
        </div>
        <Link
          href="/problems/new"
          className="inline-flex items-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-300 transition-colors"
        >
          + Tạo bài toán mới
        </Link>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="w-full sm:w-72">
          <input
            type="text"
            placeholder="Tìm kiếm theo tiêu đề hoặc nội dung..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl text-sm border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>

        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          {subjects.map((sub) => (
            <button
              key={sub}
              onClick={() => setSelectedSubject(sub)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedSubject === sub
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {sub === 'all' ? 'Tất cả lĩnh vực' : sub}
            </button>
          ))}
        </div>
      </div>

      {/* Problems Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="h-60 rounded-2xl bg-slate-200 animate-pulse"></div>
          ))}
        </div>
      ) : error ? (
        <div className="p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          {error}
        </div>
      ) : filteredProblems.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-white border border-dashed border-slate-300">
          <span className="text-4xl block mb-2">🔍</span>
          <h3 className="text-base font-semibold text-slate-800">Không tìm thấy bài toán nào</h3>
          <p className="text-sm text-slate-500 mt-1 mb-6">
            Thử thay đổi từ khóa tìm kiếm hoặc lọc lại theo lĩnh vực khác.
          </p>
          <button
            onClick={() => {
              setSearchTerm('');
              setSelectedSubject('all');
            }}
            className="px-4 py-2 text-sm text-indigo-600 hover:underline font-medium"
          >
            Đặt lại bộ lọc
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProblems.map((prob) => (
            <Link
              key={prob.id}
              href={`/problems/${prob.id}`}
              className="group block p-6 rounded-2xl bg-white border border-slate-200 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all flex flex-col justify-between"
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

                <div className="text-sm text-slate-600 line-clamp-4 overflow-hidden mb-4">
                  <MathRenderer content={prob.statement_original} />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 text-xs text-slate-400 flex justify-between items-center">
                <span>{new Date(prob.created_at).toLocaleDateString('vi-VN')}</span>
                <span className="group-hover:translate-x-1 transition-transform font-medium text-indigo-600">
                  Xem chi tiết &rarr;
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
