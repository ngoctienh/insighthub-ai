import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock, Globe, Sparkles } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { PublicRoadmapItem, RoadmapStatus } from "../types";

const COLUMNS: { status: RoadmapStatus; title: string; badge: string; icon: JSX.Element }[] = [
  {
    status: "PLANNED",
    title: "Planned — Đã lên kế hoạch",
    badge: "bg-amber-50 text-amber-800 border-amber-200",
    icon: <Clock className="w-4 h-4 text-amber-600" />,
  },
  {
    status: "IN_PROGRESS",
    title: "In Progress — Đang phát triển",
    badge: "bg-blue-50 text-blue-800 border-blue-200",
    icon: <Sparkles className="w-4 h-4 text-blue-600" />,
  },
  {
    status: "COMPLETED",
    title: "Completed — Đã ra mắt",
    badge: "bg-emerald-50 text-emerald-800 border-emerald-200",
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
  },
];

export function PublicRoadmapPage() {
  const { user, isInternal } = useAuth();
  const [items, setItems] = useState<PublicRoadmapItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<PublicRoadmapItem[]>("/roadmap/public/")
      .then((res) => setItems(res.data || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 font-bold text-slate-900">
              <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
                <Globe className="w-4 h-4 text-white" />
              </div>
              Public Product Roadmap
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {user ? (
              <Link
                to={isInternal ? "/roadmap" : "/portal"}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-600 text-white text-xs sm:text-sm font-semibold hover:bg-brand-700"
              >
                <ArrowLeft className="w-4 h-4" />
                {isInternal ? "Về Roadmap nội bộ" : "Về Customer Portal"}
              </Link>
            ) : (
              <Link
                to="/login"
                className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold"
              >
                Đăng nhập để gửi góp ý
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="mb-8 max-w-2xl">
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Lộ trình Cải tiến Sản phẩm Công khai
          </h1>
          <p className="text-slate-600 mt-2 text-sm">
            Cập nhật minh bạch những tính năng và bản sửa lỗi được ưu tiên trực tiếp từ phản hồi của cộng đồng người dùng.
          </p>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-3 gap-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-80 rounded-2xl bg-white border border-slate-200 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {COLUMNS.map((col) => {
              const colItems = items.filter((item) => item.status === col.status);
              return (
                <div
                  key={col.status}
                  className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3"
                >
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-2 font-bold text-sm text-slate-900">
                      {col.icon}
                      {col.title}
                    </div>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                      {colItems.length}
                    </span>
                  </div>

                  {colItems.length === 0 ? (
                    <p className="text-xs text-slate-400 py-6 text-center">Chưa có hạng mục nào.</p>
                  ) : (
                    colItems.map((item) => (
                      <div
                        key={item.id}
                        className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-2"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono font-bold text-brand-600">{item.code}</span>
                          <span className={`px-2 py-0.5 rounded-full border font-semibold ${col.badge}`}>
                            {item.quarter}
                          </span>
                        </div>
                        <h3 className="font-bold text-sm text-slate-900">{item.title}</h3>
                        <p className="text-xs text-slate-600 leading-relaxed">{item.summary}</p>
                        <div className="pt-1">
                          <div className="flex justify-between text-[11px] text-slate-500 mb-1">
                            <span>{item.total_linked_feedbacks} góp ý liên quan</span>
                            <span>{item.progress_percent}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-brand-600"
                              style={{ width: `${item.progress_percent}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
