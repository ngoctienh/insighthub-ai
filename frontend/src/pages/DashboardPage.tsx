import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Inbox,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, StatusBadge } from "../components/Badges";
import { DashboardData, Product } from "../types";

const SOURCE_COLORS: Record<string, string> = {
  WEB_FORM: "#4f46e5",
  EMAIL: "#0891b2",
  LIVE_CHAT: "#10b981",
  COMMUNITY: "#8b5cf6",
};

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: "#e11d48",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#64748b",
};

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState<string>("");
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Product[]>("/products/").then((r) => setProducts(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .get<DashboardData>("/dashboard/", {
        params: {
          days,
          ...(productId ? { product: productId } : {}),
        },
      })
      .then((res) => {
        if (active) setData(res.data);
      })
      .catch((err) => {
        if (active) setError(getApiErrorMessage(err, "Không thể tải dữ liệu Dashboard."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [productId, days]);

  const kpiCards = data
    ? [
        { label: "Tổng số Feedback", value: data.kpis.total_feedbacks, icon: Inbox, tone: "text-brand-600 bg-brand-50" },
        { label: "Feedback Mới", value: data.kpis.new_feedbacks, icon: TrendingUp, tone: "text-sky-600 bg-sky-50" },
        { label: "Insight Đã Phát Hiện", value: data.kpis.insights_detected, icon: Sparkles, tone: "text-violet-600 bg-violet-50" },
        { label: "Đang Xử Lý", value: data.kpis.in_progress_issues, icon: Clock, tone: "text-amber-600 bg-amber-50" },
        { label: "Đã Hoàn Thành", value: data.kpis.completed_issues, icon: CheckCircle2, tone: "text-emerald-600 bg-emerald-50" },
        { label: "Trùng Lặp Xác Nhận", value: data.kpis.duplicate_feedbacks, icon: Copy, tone: "text-slate-600 bg-slate-100" },
      ]
    : [];

  return (
    <AppLayout
      title="Product Discovery Dashboard"
      subtitle="Tổng quan phản hồi đa nguồn, nhóm Insight AI và mức độ ưu tiên thực tế từ PostgreSQL"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm text-slate-700"
          >
            <option value="">Tất cả sản phẩm</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm text-slate-700"
          >
            <option value={14}>14 ngày gần nhất</option>
            <option value={30}>30 ngày gần nhất</option>
            <option value={60}>60 ngày gần nhất</option>
          </select>
        </div>
      }
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          {error}
        </div>
      )}

      {loading || !data ? (
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div key={idx} className="h-28 rounded-2xl bg-white border border-slate-200 animate-pulse p-4" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {/* KPI Row */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {kpiCards.map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.label}
                  className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm hover:border-slate-300 transition-colors"
                >
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${card.tone}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-900">{card.value}</div>
                  <div className="text-xs text-slate-500 mt-0.5 font-medium">{card.label}</div>
                </div>
              );
            })}
          </div>

          {/* Charts Row */}
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-slate-900">Xu hướng Feedback theo thời gian</h2>
                  <p className="text-xs text-slate-500">Số lượng phản hồi tiếp nhận mỗi ngày</p>
                </div>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.feedbacks_by_date}>
                    <defs>
                      <linearGradient id="fbColor" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => String(v).slice(5)} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Area type="monotone" dataKey="count" name="Feedback" stroke="#4f46e5" strokeWidth={2} fill="url(#fbColor)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h2 className="font-bold text-slate-900">Phân bổ theo Nguồn tiếp nhận</h2>
              <p className="text-xs text-slate-500 mb-3">Website Form, Email, Live Chat, Cộng đồng</p>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.feedbacks_by_source}
                      dataKey="count"
                      nameKey="name"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                    >
                      {data.feedbacks_by_source.map((entry) => (
                        <Cell
                          key={entry.source_code}
                          fill={SOURCE_COLORS[entry.source_code] || "#6366f1"}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {data.feedbacks_by_source.map((src) => (
                  <div key={src.source_code} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg px-2.5 py-1.5">
                    <span className="flex items-center gap-1.5 truncate">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: SOURCE_COLORS[src.source_code] || "#6366f1" }}
                      />
                      {src.name}
                    </span>
                    <span className="font-bold text-slate-800">{src.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Priority Chart + Top 5 Issues + Urgent Insights */}
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h2 className="font-bold text-slate-900">Insight theo Mức độ Ưu tiên</h2>
              <p className="text-xs text-slate-500 mb-4">Phân loại theo điểm Priority (0–100)</p>
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.by_priority}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="level" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" name="Số Insight" radius={[6, 6, 0, 0]}>
                      {data.by_priority.map((item) => (
                        <Cell key={item.level} fill={PRIORITY_COLORS[item.level] || "#6366f1"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-slate-900">Top 5 Vấn đề phản ánh nhiều nhất</h2>
                  <p className="text-xs text-slate-500">Xếp hạng theo số lượng feedback</p>
                </div>
                <Link to="/insights" className="text-xs font-semibold text-brand-600 hover:underline">
                  Xem tất cả
                </Link>
              </div>
              {data.top_5_issues.length === 0 ? (
                <p className="text-sm text-slate-500 py-8 text-center">Chưa có insight nào.</p>
              ) : (
                <div className="space-y-3">
                  {data.top_5_issues.map((issue, idx) => (
                    <Link
                      key={issue.id}
                      to={`/insights/${issue.id}`}
                      className="block p-3 rounded-xl border border-slate-200 hover:border-brand-300 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-brand-600">
                            #{idx + 1} · {issue.code}
                          </div>
                          <div className="text-sm font-semibold text-slate-900 truncate mt-0.5">
                            {issue.title}
                          </div>
                        </div>
                        <PriorityBadge level={issue.priority_level} score={issue.priority_score} />
                      </div>
                      <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                        <span>{issue.feedback_count} feedback</span>
                        <span>·</span>
                        <span>{issue.affected_customers_count} khách hàng</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <h2 className="font-bold text-slate-900">Insight cần xử lý khẩn cấp</h2>
                </div>
                <Link to="/kanban" className="text-xs font-semibold text-brand-600 hover:underline">
                  Kanban
                </Link>
              </div>
              {data.urgent_insights.length === 0 ? (
                <p className="text-sm text-slate-500 py-8 text-center">Không có insight khẩn cấp tồn đọng.</p>
              ) : (
                <div className="space-y-3">
                  {data.urgent_insights.map((ins) => (
                    <Link
                      key={ins.id}
                      to={`/insights/${ins.id}`}
                      className="block p-3 rounded-xl border border-rose-100 bg-rose-50/40 hover:bg-rose-50 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-xs font-bold text-slate-600">{ins.code}</span>
                        <PriorityBadge level={ins.priority_level} score={ins.priority_score} />
                      </div>
                      <div className="text-sm font-semibold text-slate-900 line-clamp-2">{ins.title}</div>
                      <div className="mt-2 flex items-center justify-between text-xs">
                        <StatusBadge status={ins.status} />
                        <span className="text-slate-500">
                          {ins.due_date ? `Hạn: ${ins.due_date}` : `${ins.feedback_count} phản hồi`}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
