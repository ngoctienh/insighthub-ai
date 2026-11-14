import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { useToast } from "../contexts/ToastContext";
import { NotificationItem } from "../types";

export function NotificationsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ results: NotificationItem[] }>("/notifications/", {
        params: { page_size: 50, ...(unreadOnly ? { unread_only: "true" } : {}) },
      });
      setItems(res.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, [unreadOnly]);

  const markRead = async (item: NotificationItem) => {
    try {
      if (!item.is_read) {
        await api.post(`/notifications/${item.id}/mark_read/`, {});
        setItems((prev) => prev.map((x) => (x.id === item.id ? { ...x, is_read: true } : x)));
      }
      if (item.link_url) {
        navigate(item.link_url);
      }
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const markAllRead = async () => {
    try {
      await api.post("/notifications/mark_all_read/", {});
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
      showToast("Đã đánh dấu tất cả thông báo là đã đọc.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title="Trung tâm Thông báo"
      subtitle="Theo dõi cập nhật tiếp nhận, phân công, xác nhận Insight và thay đổi Product Roadmap"
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={() => setUnreadOnly((v) => !v)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold ${
              unreadOnly ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-300"
            }`}
          >
            {unreadOnly ? "Đang lọc: Chưa đọc" : "Lọc chưa đọc"}
          </button>
          <button
            onClick={markAllRead}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold hover:bg-brand-700"
          >
            <CheckCheck className="w-4 h-4" />
            Đánh dấu tất cả đã đọc
          </button>
        </div>
      }
    >
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <Bell className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-700">Bạn chưa có thông báo nào</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 divide-y divide-slate-100 shadow-sm overflow-hidden">
          {items.map((n) => (
            <div
              key={n.id}
              onClick={() => markRead(n)}
              className={`p-4 flex items-start justify-between gap-4 cursor-pointer transition-colors hover:bg-slate-50 ${
                !n.is_read ? "bg-indigo-50/40" : ""
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${
                    !n.is_read ? "bg-brand-600" : "bg-slate-300"
                  }`}
                />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-sm text-slate-900">{n.title}</span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                      {n.event_type}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600 mt-0.5">{n.message}</p>
                  <div className="text-xs text-slate-400 mt-1">
                    {n.actor_name} · {new Date(n.created_at).toLocaleString("vi-VN")}
                  </div>
                </div>
              </div>
              {!n.is_read && (
                <span className="text-xs font-semibold text-brand-600 shrink-0">Mới</span>
              )}
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
