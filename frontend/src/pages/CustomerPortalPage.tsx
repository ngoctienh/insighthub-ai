import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, CheckCircle2, Globe, Send, Sparkles } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Feedback, NotificationItem, Product, Tag } from "../types";

const STEP_ORDER = ["NEW", "ANALYZING", "PLANNED", "IN_PROGRESS", "COMPLETED"];

export function CustomerPortalPage() {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [products, setProducts] = useState<Product[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [myFeedbacks, setMyFeedbacks] = useState<Feedback[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    product: "",
    title: "",
    content: "",
    impact_level: "MEDIUM",
    tag_ids: [] as number[],
  });

  const loadPortal = async () => {
    setLoading(true);
    try {
      const [prodRes, tagRes, fbRes, notifRes] = await Promise.all([
        api.get<Product[]>("/products/"),
        api.get<Tag[]>("/tags/"),
        api.get<{ results: Feedback[] }>("/feedbacks/?page_size=20"),
        api.get<{ results: NotificationItem[] }>("/notifications/?page_size=5"),
      ]);
      setProducts(prodRes.data || []);
      if (prodRes.data[0] && !form.product) {
        setForm((prev) => ({ ...prev, product: String(prodRes.data[0].id) }));
      }
      setTags(tagRes.data || []);
      setMyFeedbacks(fbRes.data.results || []);
      setNotifications(notifRes.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPortal();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/feedbacks/", {
        product: Number(form.product),
        source_code: "WEB_FORM",
        title: form.title,
        content: form.content,
        impact_level: form.impact_level,
        tag_ids: form.tag_ids,
      });
      showToast("Đã gửi phản hồi thành công! Đội ngũ sản phẩm sẽ sớm xem xét.", "success");
      setForm((prev) => ({ ...prev, title: "", content: "", tag_ids: [] }));
      loadPortal();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppLayout
      title={`Xin chào, ${user?.display_name}`}
      subtitle="Cổng gửi góp ý, báo lỗi và theo dõi tiến độ xử lý phản hồi của riêng bạn"
      actions={
        <Link
          to="/public-roadmap"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-300 bg-white text-sm font-semibold hover:bg-slate-50"
        >
          <Globe className="w-4 h-4 text-brand-600" />
          Xem Public Roadmap
        </Link>
      }
    >
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Submit Form */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h2 className="font-bold text-slate-900 flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4 text-brand-600" />
              Gửi phản hồi mới
            </h2>
            <form onSubmit={handleSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Sản phẩm</label>
                <select
                  value={form.product}
                  onChange={(e) => setForm({ ...form, product: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Mức độ ảnh hưởng</label>
                <select
                  value={form.impact_level}
                  onChange={(e) => setForm({ ...form, impact_level: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="LOW">Low — Góp ý nhỏ</option>
                  <option value="MEDIUM">Medium — Gây bất tiện</option>
                  <option value="HIGH">High — Ảnh hưởng trải nghiệm chính</option>
                  <option value="CRITICAL">Critical — Không thể sử dụng tính năng</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Tiêu đề ngắn gọn</label>
                <input
                  type="text"
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="Ví dụ: Không nhận được thông báo tài xế tới"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Mô tả chi tiết</label>
                <textarea
                  rows={4}
                  required
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  placeholder="Kể lại tình huống bạn gặp phải hoặc điều bạn mong muốn cải thiện..."
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Chủ đề liên quan</label>
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((t) => {
                    const active = form.tag_ids.includes(t.id);
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() =>
                          setForm((prev) => ({
                            ...prev,
                            tag_ids: active
                              ? prev.tag_ids.filter((x) => x !== t.id)
                              : [...prev.tag_ids, t.id],
                          }))
                        }
                        className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                          active
                            ? "bg-brand-600 text-white border-brand-600"
                            : "bg-slate-50 text-slate-700 border-slate-200"
                        }`}
                      >
                        {t.name}
                      </button>
                    );
                  })}
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-60"
              >
                <Send className="w-4 h-4" />
                {submitting ? "Đang gửi..." : "Gửi Feedback"}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                <Bell className="w-4 h-4 text-brand-600" />
                Thông báo của bạn
              </h3>
              <Link to="/notifications" className="text-xs font-semibold text-brand-600 hover:underline">
                Xem tất cả
              </Link>
            </div>
            {notifications.length === 0 ? (
              <p className="text-xs text-slate-400">Chưa có thông báo mới.</p>
            ) : (
              <div className="space-y-2.5">
                {notifications.map((n) => (
                  <div key={n.id} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                    <div className="font-semibold text-slate-900">{n.title}</div>
                    <div className="text-slate-600 mt-0.5">{n.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* My Feedbacks & Progress Tracker */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-bold text-slate-900">Phản hồi của tôi ({myFeedbacks.length})</h2>
              <p className="text-xs text-slate-500">Nhấn vào từng mục để trao đổi hoặc bổ sung thông tin</p>
            </div>
            <Link to="/inbox" className="text-xs font-semibold text-brand-600 hover:underline">
              Xem danh sách đầy đủ
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-28 rounded-xl bg-slate-100 animate-pulse" />
              ))}
            </div>
          ) : myFeedbacks.length === 0 ? (
            <p className="text-sm text-slate-500 py-10 text-center">
              Bạn chưa gửi phản hồi nào. Hãy sử dụng biểu mẫu bên cạnh để đóng góp ý kiến đầu tiên!
            </p>
          ) : (
            <div className="space-y-4">
              {myFeedbacks.map((fb) => {
                const currentIdx = Math.max(0, STEP_ORDER.indexOf(fb.status));
                return (
                  <Link
                    key={fb.id}
                    to={`/inbox/${fb.id}`}
                    className="block p-4 rounded-xl border border-slate-200 hover:border-brand-300 hover:bg-slate-50/70 transition-all"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-brand-600">{fb.code}</span>
                        <StatusBadge status={fb.status} />
                        <PriorityBadge level={fb.impact_level} />
                      </div>
                      <span className="text-xs text-slate-400">
                        {new Date(fb.submitted_at).toLocaleDateString("vi-VN")}
                      </span>
                    </div>
                    <h3 className="font-bold text-sm text-slate-900">{fb.title}</h3>
                    <p className="text-xs text-slate-600 mt-1 line-clamp-2">{fb.content}</p>

                    {/* 5-step tracker */}
                    <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-5 gap-1">
                      {STEP_ORDER.map((step, idx) => {
                        const reached = idx <= currentIdx;
                        return (
                          <div key={step} className="flex flex-col items-center">
                            <div
                              className={`w-full h-1.5 rounded-full ${
                                reached ? "bg-brand-600" : "bg-slate-200"
                              }`}
                            />
                            <span className="text-[10px] mt-1 text-slate-500 flex items-center gap-0.5">
                              {step === "COMPLETED" && reached && <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />}
                              {step}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
