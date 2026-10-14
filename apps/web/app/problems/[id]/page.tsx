'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchProblemById, createRun, ProblemDetail, Run } from '@/lib/api';
import MathRenderer from '@/components/MathRenderer';

export default function ProblemDetailPage() {
  const params = useParams();
  const problemId = params?.id as string;

  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRawLatex, setShowRawLatex] = useState(false);
  const [copied, setCopied] = useState(false);

  // Run creation states
  const [creatingRun, setCreatingRun] = useState(false);
  const [budgetUsd, setBudgetUsd] = useState<number>(1.0);
  const [runSuccessNotice, setRunSuccessNotice] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      if (!problemId) return;
      try {
        setLoading(true);
        const data = await fetchProblemById(problemId);
        setProblem(data);
      } catch (err: any) {
        setError(err.message || 'Không thể tải chi tiết bài toán');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [problemId]);

  const handleCopyRaw = () => {
    if (!problem) return;
    navigator.clipboard.writeText(problem.statement_original);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCreateRun = async () => {
    if (!problem) return;
    try {
      setCreatingRun(true);
      setRunSuccessNotice(null);
      const newRun = await createRun(problem.id, { budget_usd: budgetUsd });
      // Thêm Run mới vào đầu danh sách
      setProblem((prev) => (prev ? { ...prev, runs: [newRun, ...prev.runs] } : prev));
      setRunSuccessNotice(`Đã tạo thành công phiên Run thử nghiệm #${newRun.id.slice(0, 8)} ở trạng thái 'queued'.`);
    } catch (err: any) {
      alert(`Lỗi khi tạo Run: ${err.message}`);
    } finally {
      setCreatingRun(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-slate-200 rounded-lg"></div>
        <div className="h-64 bg-slate-200 rounded-2xl"></div>
        <div className="h-48 bg-slate-200 rounded-2xl"></div>
      </div>
    );
  }

  if (error || !problem) {
    return (
      <div className="text-center py-16 px-4 bg-white rounded-2xl border border-slate-200">
        <span className="text-4xl block mb-3">⚠️</span>
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy bài toán</h2>
        <p className="text-sm text-slate-500 mt-2 mb-6">
          {error || 'Bài toán có thể đã bị xóa hoặc đường dẫn không chính xác.'}
        </p>
        <Link
          href="/problems"
          className="px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
        >
          Quay lại danh sách bài toán
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Breadcrumb Navigation */}
      <nav className="text-xs text-slate-500 flex items-center space-x-2">
        <Link href="/" className="hover:text-indigo-600 transition-colors">
          Trang chủ
        </Link>
        <span>/</span>
        <Link href="/problems" className="hover:text-indigo-600 transition-colors">
          Kho bài toán
        </Link>
        <span>/</span>
        <span className="text-slate-800 font-medium truncate max-w-xs sm:max-w-md">
          {problem.title || `Bài toán #${problem.id.slice(0, 8)}`}
        </span>
      </nav>

      {/* Main Problem Details Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Header Bar */}
        <div className="p-6 sm:p-8 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {problem.subject && (
                <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
                  {problem.subject}
                </span>
              )}
              {problem.difficulty && (
                <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 text-slate-700">
                  {problem.difficulty}
                </span>
              )}
              <span className="text-xs text-slate-400">
                Tạo lúc: {new Date(problem.created_at).toLocaleString('vi-VN')}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {problem.title || 'Bài toán không tiêu đề'}
            </h1>
          </div>

          {/* Toggle View Raw LaTeX / Rendered */}
          <div className="flex items-center space-x-2 self-start sm:self-auto">
            <button
              onClick={() => setShowRawLatex(!showRawLatex)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 transition-colors flex items-center space-x-1.5"
            >
              <span>{showRawLatex ? '👁️ Xem kết xuất LaTeX' : '</> Xem raw LaTeX'}</span>
            </button>
            {showRawLatex && (
              <button
                onClick={handleCopyRaw}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
              >
                {copied ? '✓ Đã sao chép!' : 'Sao chép LaTeX'}
              </button>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 sm:p-8 bg-slate-50/50">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
            Nội dung đề bài gốc:
          </h2>

          {showRawLatex ? (
            <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-sm overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {problem.statement_original}
            </pre>
          ) : (
            <div className="p-6 rounded-xl bg-white border border-slate-200 text-base leading-relaxed text-slate-800 shadow-sm">
              <MathRenderer content={problem.statement_original} />
            </div>
          )}
        </div>
      </div>

      {/* Action Banner: Run Trigger */}
      <div className="bg-gradient-to-r from-indigo-50 via-slate-50 to-indigo-50/30 p-6 sm:p-8 rounded-2xl border border-indigo-100 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-1">
          <div className="inline-flex items-center space-x-2 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">
            <span>⚙️ Chế độ Bước 2</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900">Khởi tạo phiên giải toán (Run)</h3>
          <p className="text-sm text-slate-600 max-w-xl">
            Tạo một bản ghi Run ở trạng thái <code>queued</code> cho bài toán này. Hệ thống ở Bước 2
            xác thực toàn vẹn quy trình mà không gọi AI thực tế.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <span className="text-xs font-medium text-slate-500 whitespace-nowrap">Ngân sách ($):</span>
            <input
              type="number"
              step="0.1"
              min="0"
              value={budgetUsd}
              onChange={(e) => setBudgetUsd(parseFloat(e.target.value) || 0)}
              className="w-24 px-3 py-2 text-sm rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          <button
            onClick={handleCreateRun}
            disabled={creatingRun}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 whitespace-nowrap"
          >
            {creatingRun ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                <span>Đang khởi tạo...</span>
              </>
            ) : (
              <span>🚀 Tạo Run thử nghiệm</span>
            )}
          </button>
        </div>
      </div>

      {runSuccessNotice && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center space-x-2">
          <span>✓</span>
          <span>{runSuccessNotice}</span>
        </div>
      )}

      {/* Runs History List */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h2 className="text-xl font-bold text-slate-900">Lịch sử các phiên giải toán (Runs)</h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">
              {problem.runs.length}
            </span>
          </div>
        </div>

        {problem.runs.length === 0 ? (
          <div className="text-center py-12 px-4 rounded-2xl bg-white border border-dashed border-slate-300">
            <span className="text-3xl block mb-2">⏱️</span>
            <h4 className="text-base font-semibold text-slate-800">Chưa có lượt chạy nào</h4>
            <p className="text-xs text-slate-500 mt-1 mb-4">
              Nhấn nút &ldquo;Tạo Run thử nghiệm&rdquo; ở trên để bắt đầu phiên giải toán đầu tiên cho bài này.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {problem.runs.map((run: Run) => (
              <div
                key={run.id}
                className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Status Badge */}
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                      <span className="w-2 h-2 mr-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                      Trạng thái: {run.status}
                    </span>

                    {/* Mandatory Label "Chưa chạy AI" */}
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-800 border border-purple-200">
                      ⚡ {run.ai_notice || 'Chưa chạy AI'}
                    </span>

                    <span className="text-xs text-slate-400 font-mono">
                      ID: {run.id}
                    </span>
                  </div>

                  <div className="text-xs text-slate-500 flex flex-wrap gap-4">
                    <span>
                      <strong>Thời điểm tạo:</strong> {new Date(run.created_at).toLocaleString('vi-VN')}
                    </span>
                    <span>
                      <strong>Ngân sách:</strong> ${Number(run.budget_usd || 0).toFixed(2)} USD
                    </span>
                    <span>
                      <strong>Chi phí thực tế:</strong> ${Number(run.actual_cost_usd || 0).toFixed(6)} USD
                    </span>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                  {/* Run Configuration summary */}
                  <div className="bg-slate-50 px-3 py-2 rounded-xl border border-slate-100 text-[11px] text-slate-600 font-mono">
                    <span>Chế độ: {run.config?.mode || 'step3_council'}</span>
                    <span className="block text-slate-400">
                      AI Enabled: {String(run.config?.ai_enabled ?? true)}
                    </span>
                  </div>

                  <Link
                    href={`/runs/${run.id}`}
                    className="px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-all flex items-center gap-1.5"
                  >
                    <span>Xem Hội đồng AI</span>
                    <span>→</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
