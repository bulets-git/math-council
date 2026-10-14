'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  fetchRunById,
  fetchRunSolutions,
  fetchRunChallenges,
  fetchRunReport,
  fetchRunUsage,
  fetchRunMessages,
  cancelRun,
  resumeRun,
  Run,
  SolutionDetail,
  Challenge,
  FinalReport,
  UsageSummary,
  Message,
} from '@/lib/api';
import MathRenderer from '@/components/MathRenderer';

const PIPELINE_STEPS = [
  { key: 'queued', label: 'Hàng đợi', icon: '⏳' },
  { key: 'normalizing', label: 'Chuẩn hóa đề', icon: '🔍' },
  { key: 'retrieving_source', label: 'Tìm nguồn đề', icon: '🌐' },
  { key: 'solving', label: 'Giải song song (A & B)', icon: '✏️' },
  { key: 'critiquing', label: 'Phản biện (Skeptic)', icon: '🛡️' },
  { key: 'revising', label: 'Sửa chữa lời giải', icon: '🔄' },
  { key: 'adjudicating', label: 'Thẩm định (Judge)', icon: '⚖️' },
  { key: 'completed', label: 'Hoàn thành', icon: '✅' },
];

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params?.id as string;

  const [run, setRun] = useState<Run | null>(null);
  const [solutions, setSolutions] = useState<SolutionDetail[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [report, setReport] = useState<FinalReport | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const [activeTab, setActiveTab] = useState<'solutions' | 'challenges' | 'report' | 'usage' | 'messages'>('solutions');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveConnected, setLiveConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // Load initial data
  const loadRunData = async (id: string) => {
    try {
      const runData = await fetchRunById(id);
      setRun(runData);

      // Load related Step 3 entities
      const [sols, chs, rep, usg, msgs] = await Promise.allSettled([
        fetchRunSolutions(id),
        fetchRunChallenges(id),
        fetchRunReport(id),
        fetchRunUsage(id),
        fetchRunMessages(id),
      ]);

      if (sols.status === 'fulfilled') setSolutions(sols.value);
      if (chs.status === 'fulfilled') setChallenges(chs.value);
      if (rep.status === 'fulfilled') setReport(rep.value);
      if (usg.status === 'fulfilled') setUsage(usg.value);
      if (msgs.status === 'fulfilled') setMessages(msgs.value);
    } catch (err: any) {
      setError(err.message || 'Không thể tải chi tiết Run');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!runId) return;
    loadRunData(runId);

    // Setup SSE connection
    const sseUrl = `/api/v1/runs/${runId}/events`;
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setLiveConnected(true);
    };

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setLastEvent(`${payload.event_type} (${new Date().toLocaleTimeString()})`);
        
        // Refresh data on pipeline progression
        if (payload.event_type === 'status_changed') {
          setRun((prev) => (prev ? { ...prev, status: payload.data?.status || prev.status } : prev));
        }
        
        // Always refresh datasets when events occur
        loadRunData(runId);

        if (['completed', 'failed', 'cancelled', 'budget_exhausted'].includes(payload.data?.status)) {
          es.close();
          setLiveConnected(false);
        }
      } catch (e) {
        // Ignored unparsable SSE ping
      }
    };

    es.onerror = () => {
      setLiveConnected(false);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId]);

  const handleCancel = async () => {
    if (!run) return;
    if (!confirm('Bạn có chắc chắn muốn hủy phiên giải toán này?')) return;
    try {
      setActionLoading(true);
      const updated = await cancelRun(run.id);
      setRun(updated);
      alert('Đã hủy phiên giải toán thành công.');
    } catch (err: any) {
      alert(`Lỗi khi hủy phiên: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!run) return;
    try {
      setActionLoading(true);
      const updated = await resumeRun(run.id);
      setRun(updated);
      await loadRunData(run.id);
      alert('Đã tiếp tục phiên giải toán.');
    } catch (err: any) {
      alert(`Lỗi khi tiếp tục phiên: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-slate-200 rounded-lg"></div>
        <div className="h-24 bg-slate-200 rounded-2xl"></div>
        <div className="h-96 bg-slate-200 rounded-2xl"></div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="text-center py-16 px-4 bg-white rounded-2xl border border-slate-200">
        <span className="text-4xl block mb-3">⚠️</span>
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy thông tin Run</h2>
        <p className="text-sm text-slate-500 mt-2 mb-6">{error || 'ID phiên giải toán không hợp lệ.'}</p>
        <Link
          href="/problems"
          className="px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
        >
          Quay lại danh sách bài toán
        </Link>
      </div>
    );
  }

  const currentStepIdx = PIPELINE_STEPS.findIndex((s) => s.key === run.status);
  const isTerminated = ['completed', 'failed', 'cancelled', 'budget_exhausted'].includes(run.status);
  const isNeedsReview = run.status === 'needs_review';
  const discoveredSource = run.config?.discovered_source;

  return (
    <div className="space-y-8">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <nav className="text-xs text-slate-500 flex items-center space-x-2 mb-2">
            <Link href="/" className="hover:text-indigo-600 transition-colors">
              Trang chủ
            </Link>
            <span>/</span>
            <Link href={`/problems/${run.problem_id}`} className="hover:text-indigo-600 transition-colors">
              Bài toán
            </Link>
            <span>/</span>
            <span className="text-slate-800 font-medium font-mono">Run #{run.id.slice(0, 8)}</span>
          </nav>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Hội đồng Tranh luận Toán học
            </h1>
            <span className="font-mono text-xs px-2.5 py-1 bg-slate-100 text-slate-600 rounded-lg border border-slate-200">
              ID: {run.id}
            </span>
          </div>
        </div>

        {/* Live SSE status indicator and Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-white border border-slate-200 shadow-sm">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                liveConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
              }`}
            />
            <span className={liveConnected ? 'text-emerald-700' : 'text-slate-500'}>
              {liveConnected ? 'Live SSE Đang kết nối' : 'Đã ngắt kết nối Live'}
            </span>
            {lastEvent && <span className="text-[10px] text-slate-400 ml-1">({lastEvent})</span>}
          </div>

          {/* Action buttons */}
          {isNeedsReview && (
            <button
              onClick={handleResume}
              disabled={actionLoading}
              className="px-4 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white shadow-sm transition-all"
            >
              ▶ Tiếp tục chạy (Resume)
            </button>
          )}

          {!isTerminated && !isNeedsReview && (
            <button
              onClick={handleCancel}
              disabled={actionLoading}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition-all"
            >
              ⛔ Hủy phiên (Cancel)
            </button>
          )}
        </div>
      </div>

      {/* State Machine Status Bar */}
      <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
            <span>Tiến trình Hội đồng (State Machine)</span>
            <span className="text-xs normal-case font-mono font-medium px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-100">
              Trạng thái: {run.status}
            </span>
          </h2>
          <div className="text-xs text-slate-500">
            Ngân sách: <strong>${Number(run.actual_cost_usd || 0).toFixed(4)}</strong> / ${Number(run.budget_usd || 1).toFixed(2)} USD
          </div>
        </div>

        {/* Special Status Banner for Divergent States */}
        {isNeedsReview && (
          <div className="mb-5 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">⚠️</span>
              <div>
                <strong>Cần người dùng xem xét (needs_review):</strong> Bộ chuẩn hóa phát hiện dấu hiệu mập mờ hoặc lỗi chép đề. Vui lòng kiểm tra và bấm "Tiếp tục chạy" để tiến hành giải.
              </div>
            </div>
            <button
              onClick={handleResume}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg bg-amber-600 text-white font-bold text-xs hover:bg-amber-700"
            >
              Tiếp tục giải
            </button>
          </div>
        )}

        {run.status === 'budget_exhausted' && (
          <div className="mb-5 p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs flex items-center gap-2">
            <span className="text-xl">🛑</span>
            <div>
              <strong>Ngân sách đã cạn (budget_exhausted):</strong> Tổng chi phí các Agent vượt quá ngân sách ${Number(run.budget_usd).toFixed(2)} USD được phân bổ.
            </div>
          </div>
        )}

        {run.status === 'failed' && (
          <div className="mb-5 p-5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-950 text-xs shadow-sm">
            <div className="flex items-start gap-3">
              <span className="text-2xl flex-shrink-0">❌</span>
              <div className="space-y-2 flex-grow">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <strong className="text-sm font-bold text-rose-900">
                    Phiên giải toán thất bại (Failed) {run.config?.failure_stage ? `tại bước: ${run.config.failure_stage}` : ''}
                  </strong>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-rose-100 text-rose-800 border border-rose-200">
                    Mode: {run.config?.mode || 'live'}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-white/90 border border-rose-200 text-rose-800 font-mono text-xs whitespace-pre-wrap break-words leading-relaxed">
                  {run.config?.error || 'Đã xảy ra lỗi trong quá trình thực thi AI. Vui lòng kiểm tra API Key hoặc Worker logs trên server.'}
                </div>
                <div className="text-[11px] text-rose-700 bg-rose-100/60 p-2.5 rounded-xl border border-rose-200/60">
                  💡 <strong>Cách xử lý:</strong> Nếu lỗi do thiếu API Key, truy cập <strong>Railway Dashboard</strong> &rarr; chọn service <strong>api</strong> &rarr; tab <strong>Variables</strong> và thêm ít nhất một khóa:
                  <ul className="list-disc list-inside mt-1 space-y-0.5 font-mono text-[10px]">
                    <li><code>OPENAI_COMPATIBLE_API_KEY</code>: Khóa OpenRouter (hỗ trợ tất cả mô hình Gemini, Claude, OpenAI)</li>
                    <li><code>GEMINI_API_KEY</code>: Khóa Google AI Studio (cho Normalizer &amp; Solver A)</li>
                    <li><code>OPENAI_API_KEY</code>: Khóa OpenAI (cho Solver B &amp; Judge)</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Linear Stepper */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {PIPELINE_STEPS.map((step, idx) => {
            const isCurrent = run.status === step.key;
            const isPast = currentStepIdx > idx;

            let cardBg = 'bg-slate-50 border-slate-200 text-slate-400';
            if (isCurrent) {
              cardBg = 'bg-indigo-50 border-indigo-500 text-indigo-700 font-bold ring-2 ring-indigo-200';
            } else if (isPast) {
              cardBg = 'bg-emerald-50 border-emerald-300 text-emerald-800 font-medium';
            }

            return (
              <div
                key={step.key}
                className={`p-3 rounded-xl border flex flex-col items-center text-center transition-all ${cardBg}`}
              >
                <div className="text-lg mb-1">{isPast ? '✓' : step.icon}</div>
                <div className="text-[11px] leading-tight">{step.label}</div>
              </div>
            );
          })}
        </div>

        {/* Discovered Problem Source Card */}
        {discoveredSource && discoveredSource.source_found && discoveredSource.source_metadata && (
          <div className="mt-6 p-5 rounded-2xl bg-gradient-to-br from-indigo-900/5 via-blue-900/5 to-cyan-900/5 border border-indigo-200/80 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">🌐</span>
                <h3 className="text-sm font-bold text-slate-800 tracking-tight">
                  Nguồn gốc bài toán (Problem Source)
                </h3>
                {discoveredSource.match_type === 'exact_match' ? (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                    <span>✓</span> Khớp chính xác (Exact Match)
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-200 flex items-center gap-1">
                    <span>⚠️</span> Biến thể đề thi (Modified Variant)
                  </span>
                )}
              </div>
              {discoveredSource.match_type === 'exact_match' && (
                <span className="text-xs font-mono font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-lg">
                  ⚡ Fast-Track kích hoạt (Sử dụng Lời giải chuẩn)
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-white p-3.5 rounded-xl border border-slate-200 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Kỳ thi / Giải đấu</span>
                <span className="font-bold text-slate-800 text-sm">
                  {discoveredSource.source_metadata.competition_name}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Năm & Số bài</span>
                <span className="font-bold text-slate-800 text-sm">
                  Năm {discoveredSource.source_metadata.year} &bull; Bài #{discoveredSource.source_metadata.problem_number}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Tài liệu tham khảo (AoPS / Link)</span>
                {discoveredSource.source_metadata.reference_urls && discoveredSource.source_metadata.reference_urls.length > 0 ? (
                  <div className="flex flex-wrap gap-2 mt-0.5">
                    {discoveredSource.source_metadata.reference_urls.map((url: string, idx: number) => (
                      <a
                        key={idx}
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 underline font-medium truncate max-w-[220px]"
                        title={url}
                      >
                        <span>🔗</span>
                        <span>{url.replace(/^https?:\/\//, '').split('/')[0]}...</span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <span className="text-slate-400 italic">Không có link ngoài</span>
                )}
              </div>
            </div>

            {discoveredSource.variant_warning && (
              <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
                <span className="text-base leading-none">⚠️</span>
                <div>
                  <strong>Cảnh báo biến thể (Variant Warning):</strong> {discoveredSource.variant_warning}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Tabs Bar */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-2">
          <button
            onClick={() => setActiveTab('solutions')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'solutions'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>📝 Lời giải & Mệnh đề</span>
            <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 text-[10px]">
              {solutions.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('challenges')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'challenges'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>🛡️ Phản biện Skeptic</span>
            <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 text-[10px]">
              {challenges.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('report')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'report'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>⚖️ Phán quyết của Judge</span>
            {report && <span className="w-2 h-2 rounded-full bg-emerald-500"></span>}
          </button>

          <button
            onClick={() => setActiveTab('usage')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'usage'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>📊 Chi phí & Token</span>
            <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 text-[10px]">
              {usage?.total_calls || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('messages')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'messages'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>💬 Hội thoại Council</span>
            <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 text-[10px]">
              {messages.length}
            </span>
          </button>
        </nav>
      </div>

      {/* Tab 1: Solutions & Claims */}
      {activeTab === 'solutions' && (
        <div className="space-y-6">
          {solutions.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 text-slate-500 text-sm">
              Chưa có lời giải nào được tạo ra. Đang đợi Solver A và B giải song song...
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {solutions.map((sol) => (
                <div
                  key={sol.id}
                  className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col"
                >
                  {/* Solution Card Header */}
                  <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-md text-xs font-bold uppercase bg-indigo-100 text-indigo-800">
                        {sol.solver_role}
                      </span>
                      <span className="text-xs text-slate-600 font-semibold">
                        Phiên bản v{sol.version} (Vòng {sol.round_number})
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {sol.claims.length} mệnh đề
                    </span>
                  </div>

                  <div className="p-5 space-y-4 flex-1">
                    {/* Summary */}
                    {sol.summary && (
                      <div className="text-xs text-slate-700 bg-slate-50 p-3 rounded-xl border border-slate-100">
                        <strong>Tóm tắt phương pháp:</strong> {sol.summary}
                      </div>
                    )}

                    {/* Claims DAG list */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                        Đồ thị Mệnh đề (Claims DAG):
                      </h4>
                      {sol.claims.map((claim) => {
                        let statusColor = 'bg-slate-100 text-slate-600 border-slate-200';
                        if (claim.status === 'supported') {
                          statusColor = 'bg-emerald-100 text-emerald-800 border-emerald-300';
                        } else if (claim.status === 'disputed') {
                          statusColor = 'bg-amber-100 text-amber-800 border-amber-300';
                        } else if (claim.status === 'rejected') {
                          statusColor = 'bg-rose-100 text-rose-800 border-rose-300';
                        }

                        return (
                          <div
                            key={claim.id}
                            className="p-3 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-all space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-white">
                                  {claim.claim_label}
                                </span>
                                {claim.claim_type && (
                                  <span className="text-[10px] text-slate-500 font-mono">
                                    [{claim.claim_type}]
                                  </span>
                                )}
                              </div>
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${statusColor}`}
                              >
                                {claim.status}
                              </span>
                            </div>

                            {/* Claim Content with Math */}
                            <div className="text-xs text-slate-800">
                              <MathRenderer content={claim.content} />
                            </div>

                            {/* Dependencies link */}
                            {claim.depends_on && claim.depends_on.length > 0 && (
                              <div className="text-[10px] text-slate-500 flex items-center gap-1 pt-1 border-t border-slate-100">
                                <span>🔗 Phụ thuộc vào:</span>
                                <div className="flex gap-1">
                                  {claim.depends_on.map((dep) => (
                                    <span
                                      key={dep}
                                      className="font-mono bg-slate-100 text-slate-700 px-1 rounded"
                                    >
                                      {dep}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Final Answer */}
                    {sol.final_answer && (
                      <div className="mt-4 p-3 rounded-xl bg-indigo-50 border border-indigo-100">
                        <div className="text-[11px] font-bold text-indigo-900 mb-1">
                          Đáp số cuối cùng:
                        </div>
                        <div className="text-sm font-semibold text-indigo-950">
                          <MathRenderer content={sol.final_answer} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Skeptic Challenges */}
      {activeTab === 'challenges' && (
        <div className="space-y-4">
          {challenges.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 text-slate-500 text-sm">
              Chưa có phản biện nào được ghi nhận. Skeptic sẽ phản biện sau khi hoàn tất giải toán.
            </div>
          ) : (
            challenges.map((ch) => {
              let statusBg = 'bg-amber-100 text-amber-800 border-amber-200';
              if (ch.status === 'accepted') statusBg = 'bg-rose-100 text-rose-800 border-rose-200';
              if (ch.status === 'rejected') statusBg = 'bg-emerald-100 text-emerald-800 border-emerald-200';

              return (
                <div
                  key={ch.id}
                  className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900">
                        🛡️ {ch.challenger_role}
                      </span>
                      <span className="text-xs text-slate-500">
                        (Vòng {ch.round_number})
                      </span>
                      <span className="font-mono text-xs px-2 py-0.5 bg-slate-100 rounded text-slate-700">
                        Phân loại lỗi: {ch.error_type}
                      </span>
                    </div>

                    <span className={`text-xs font-bold px-3 py-1 rounded-full border ${statusBg}`}>
                      Trạng thái: {ch.status}
                    </span>
                  </div>

                  {/* Argument */}
                  <div className="text-xs text-slate-800 bg-slate-50 p-4 rounded-xl border border-slate-100">
                    <div className="font-bold text-slate-700 mb-1">Luận cứ phản biện:</div>
                    <MathRenderer content={ch.argument} />
                  </div>

                  {/* Events audit timeline */}
                  {ch.events && ch.events.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        Lịch sử thẩm định phản biện (Challenge Events):
                      </div>
                      <div className="space-y-1.5">
                        {ch.events.map((evt) => (
                          <div
                            key={evt.id}
                            className="text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between"
                          >
                            <div>
                              <strong className="text-indigo-600">{evt.actor_role}</strong> đã chuyển từ{' '}
                              <span className="font-mono font-semibold">{evt.from_status}</span> sang{' '}
                              <span className="font-mono font-bold text-indigo-700">{evt.to_status}</span>
                              {evt.comment && <span className="text-slate-600 ml-2">— "{evt.comment}"</span>}
                            </div>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {new Date(evt.created_at).toLocaleTimeString('vi-VN')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Tab 3: Judge Final Report */}
      {activeTab === 'report' && (
        <div>
          {!report ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 text-slate-500 text-sm">
              <span className="text-3xl block mb-2">⚖️</span>
              Chưa có phán quyết cuối cùng của Judge. Báo cáo sẽ được tổng hợp khi hoàn tất bước Adjudicating.
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">⚖️</span>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">Báo cáo Phán quyết Cuối cùng</h3>
                    <div className="text-xs text-slate-500">
                      Thẩm phán: <strong>{report.judge_role}</strong> | Độ tin cậy:{' '}
                      <strong>{report.score ? `${Number(report.score) * 100}%` : 'N/A'}</strong>
                    </div>
                  </div>
                </div>

                <span className="px-3.5 py-1.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  {report.consensus_status === 'consensus_reached' ? 'Đã đạt Đồng thuận (Consensus Reached)' : report.consensus_status}
                </span>
              </div>

              {/* Executive Summary */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 space-y-1">
                <strong className="block text-slate-900 text-sm">Tóm tắt của Thẩm định viên:</strong>
                <p>{report.executive_summary}</p>
              </div>

              {/* Final LaTeX Solution */}
              <div className="space-y-2">
                <h4 className="text-sm font-bold text-slate-800">
                  Lời giải Toán học Hoàn chỉnh (Đã chuẩn hóa & thẩm định):
                </h4>
                <div className="p-6 rounded-2xl bg-indigo-50/40 border border-indigo-100 text-slate-900 leading-relaxed text-sm">
                  <MathRenderer content={report.final_latex_solution} />
                </div>
              </div>

              {/* Dissenting opinions */}
              {report.dissenting_opinions && report.dissenting_opinions.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                  <strong>Ý kiến bất đồng / bảo lưu quan điểm:</strong>
                  <ul className="list-disc pl-4 space-y-1 mt-1">
                    {report.dissenting_opinions.map((op, i) => (
                      <li key={i}>{op}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Usage & Budget */}
      {activeTab === 'usage' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <span className="text-xs text-slate-500 font-semibold uppercase">Số lần gọi LLM</span>
              <div className="text-2xl font-black text-slate-900 mt-1">
                {usage?.total_calls || 0}
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <span className="text-xs text-slate-500 font-semibold uppercase">Tổng Tokens</span>
              <div className="text-2xl font-black text-indigo-600 mt-1">
                {(usage?.total_tokens || 0).toLocaleString()}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Prompt: {usage?.total_prompt_tokens.toLocaleString()} | Completion: {usage?.total_completion_tokens.toLocaleString()}
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <span className="text-xs text-slate-500 font-semibold uppercase">Chi phí thực tế</span>
              <div className="text-2xl font-black text-emerald-600 mt-1">
                ${Number(usage?.total_cost_usd || 0).toFixed(6)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Ngân sách: ${Number(run.budget_usd || 1).toFixed(2)} USD
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <span className="text-xs text-slate-500 font-semibold uppercase">Tỷ lệ sử dụng Ngân sách</span>
              <div className="text-2xl font-black text-slate-800 mt-1">
                {((Number(usage?.total_cost_usd || 0) / Number(run.budget_usd || 1)) * 100).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Model Calls Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-4 bg-slate-50 border-b border-slate-200">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Chi tiết từng lượt gọi Agent (Audit Trail)
              </h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/50 text-slate-500 font-semibold">
                    <th className="py-3 px-4">Agent Role</th>
                    <th className="py-3 px-4">Model</th>
                    <th className="py-3 px-4">Prompt Tokens</th>
                    <th className="py-3 px-4">Completion</th>
                    <th className="py-3 px-4">Độ trễ</th>
                    <th className="py-3 px-4">Chi phí</th>
                    <th className="py-3 px-4">Version</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {usage?.calls.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4 font-bold text-slate-900">{c.agent_role}</td>
                      <td className="py-3 px-4 font-mono text-slate-500">{c.model_name}</td>
                      <td className="py-3 px-4 font-mono">{c.prompt_tokens}</td>
                      <td className="py-3 px-4 font-mono">{c.completion_tokens}</td>
                      <td className="py-3 px-4 font-mono">{c.latency_ms} ms</td>
                      <td className="py-3 px-4 font-mono font-semibold text-emerald-700">
                        ${Number(c.cost_usd).toFixed(6)}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                        {c.prompt_version}
                      </td>
                    </tr>
                  ))}
                  {(!usage?.calls || usage.calls.length === 0) && (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        Chưa có dữ liệu gọi model nào.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Messages */}
      {activeTab === 'messages' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 space-y-4">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
            Nhật ký Trao đổi giữa các Agent (Council Transcript)
          </div>
          {messages.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-xs">
              Chưa có tin nhắn nào trong hội đồng.
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                        {m.sender_role}
                      </span>
                      {m.recipient_role && (
                        <span className="text-slate-500">
                          ➔ <span className="font-semibold">{m.recipient_role}</span>
                        </span>
                      )}
                      <span className="text-slate-400">Vòng {m.round_number}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(m.created_at).toLocaleTimeString('vi-VN')}
                    </span>
                  </div>
                  <div className="text-slate-800 font-sans leading-relaxed">
                    <MathRenderer content={m.content} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
