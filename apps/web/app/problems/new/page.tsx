'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { createProblem } from '@/lib/api';
import MathRenderer from '@/components/MathRenderer';

export default function NewProblemPage() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [statement, setStatement] = useState('');
  const [subject, setSubject] = useState('Đại số');
  const [difficulty, setDifficulty] = useState('Trung bình');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subjects = ['Đại số', 'Số học', 'Hình học', 'Tổ hợp', 'Bất đẳng thức'];
  const difficulties = ['Cơ bản', 'Trung bình', 'Nâng cao', 'Olympiad / Chuyên'];

  const sampleTemplates = [
    {
      label: 'Đại số & Căn thức',
      text: 'Cho phương trình bậc hai: $ax^2 + bx + c = 0$ với $a \\neq 0$.\nNghiệm được xác định bởi công thức:\n$$x_{1,2} = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\nHãy biện luận số nghiệm của phương trình theo $\\Delta = b^2 - 4ac$.',
    },
    {
      label: 'Tích phân & Giải tích',
      text: 'Tính giá trị của tích phân sau:\n$$I = \\int_{0}^{\\frac{\\pi}{2}} \\frac{\\sin^3(x)}{\\sin(x) + \\cos(x)} \\, dx$$\nBiết kết quả có dạng $\\frac{\\pi - 1}{a}$, hãy tìm giá trị của $a \\in \\mathbb{Z}$.',
    },
    {
      label: 'Bất đẳng thức Cauchy-Schwarz',
      text: 'Cho các số thực dương $a, b, c > 0$ thỏa mãn $a + b + c = 3$.\nChứng minh bất đẳng thức sau:\n$$\\frac{a}{1 + b^2} + \\frac{b}{1 + c^2} + \\frac{c}{1 + a^2} \\ge \\frac{3}{2}$$\nDấu đẳng thức xảy ra khi nào?',
    },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statement.trim()) {
      setError('Đề toán không được để trống hoặc chỉ chứa khoảng trắng.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const res = await createProblem({
        title: title.trim() || undefined,
        statement_original: statement,
        subject,
        difficulty,
        input_type: 'text',
      });
      router.push(`/problems/${res.id}`);
    } catch (err: any) {
      setError(err.message || 'Không thể tạo bài toán. Vui lòng thử lại.');
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Breadcrumb & Title */}
      <div>
        <nav className="text-xs text-slate-500 mb-2 flex items-center space-x-2">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            Trang chủ
          </Link>
          <span>/</span>
          <Link href="/problems" className="hover:text-indigo-600 transition-colors">
            Kho bài toán
          </Link>
          <span>/</span>
          <span className="text-slate-800 font-medium">Tạo bài toán mới</span>
        </nav>
        <h1 className="text-3xl font-bold text-slate-900">Tạo bài toán mới</h1>
        <p className="text-sm text-slate-500 mt-1">
          Nhập nội dung đề bài tiếng Việt và công thức LaTeX toán học chuẩn xác
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start space-x-2">
          <span className="font-bold">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* 2-Column Responsive Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left Column: Form */}
        <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Tiêu đề bài toán <span className="text-xs font-normal text-slate-400">(Tùy chọn)</span>
              </label>
              <input
                type="text"
                placeholder="Ví dụ: Giải phương trình lượng giác nâng cao..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={300}
                className="w-full px-3.5 py-2.5 rounded-xl text-sm border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>

            {/* Subject & Difficulty Selectors */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  Lĩnh vực
                </label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl text-sm border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                >
                  {subjects.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  Độ khó
                </label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl text-sm border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                >
                  {difficulties.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Statement Original (LaTeX supported) */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-sm font-semibold text-slate-700">
                  Nội dung đề toán <span className="text-rose-500">*</span>
                </label>
                <span className="text-xs text-slate-400">
                  Hỗ trợ <code className="bg-slate-100 px-1 py-0.5 rounded">$inline$</code> và{' '}
                  <code className="bg-slate-100 px-1 py-0.5 rounded">$$block$$</code>
                </span>
              </div>
              <textarea
                required
                rows={9}
                placeholder="Nhập nội dung đề bài tại đây... Ví dụ: Cho tam giác $ABC$ vuông tại $A$..."
                value={statement}
                onChange={(e) => setStatement(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl text-sm font-mono border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 leading-relaxed"
              />
            </div>

            {/* Template Quick Insert */}
            <div>
              <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Chèn nhanh mẫu đề toán:
              </span>
              <div className="flex flex-wrap gap-2">
                {sampleTemplates.map((t, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setStatement(t.text)}
                    className="px-2.5 py-1 text-xs rounded-lg border border-slate-200 bg-slate-50 text-slate-700 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors"
                  >
                    + {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit & Cancel Buttons */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-end space-x-3">
              <Link
                href="/problems"
                className="px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Hủy
              </Link>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Đang tạo bài toán...' : 'Lưu & Khởi tạo bài toán'}
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Live Preview */}
        <div className="sticky top-24 bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                Khung Xem Trước Công Thức (Live Preview)
              </h2>
            </div>
            <span className="text-xs text-slate-400">KaTeX MathRenderer</span>
          </div>

          <div className="min-h-[360px] p-4 rounded-xl bg-slate-50/70 border border-slate-100 overflow-y-auto">
            {title && (
              <h3 className="text-lg font-bold text-slate-900 mb-3 pb-2 border-b border-slate-200/60">
                {title}
              </h3>
            )}

            {statement.trim() ? (
              <div className="prose prose-sm max-w-none text-slate-800">
                <MathRenderer content={statement} />
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-center text-slate-400 space-y-2">
                <span className="text-3xl">📐</span>
                <p className="text-sm font-medium">Chưa có nội dung xem trước</p>
                <p className="text-xs max-w-xs">
                  Gõ công thức LaTeX ở khung bên trái hoặc nhấn một trong các mẫu có sẵn để thấy kết quả hiển thị trực tiếp.
                </p>
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-500 bg-indigo-50/60 p-3 rounded-lg border border-indigo-100/60">
            💡 <strong>Mẹo:</strong> Dùng <code className="text-indigo-700 font-mono">$x^2$</code> cho công thức inline, và{' '}
            <code className="text-indigo-700 font-mono">$$\int_a^b f(x)dx$$</code> cho công thức hiển thị riêng biệt theo dòng.
          </div>
        </div>
      </div>
    </div>
  );
}
