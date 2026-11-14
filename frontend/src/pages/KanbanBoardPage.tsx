import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Calendar, MessageSquare, Send, Users, X } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ActivityLogItem, CommentItem, InsightGroup, InsightStatus, User } from "../types";

const COLUMNS: { key: InsightStatus; label: string; dot: string }[] = [
  { key: "NEW", label: "New", dot: "bg-sky-500" },
  { key: "ANALYZING", label: "Analyzing", dot: "bg-violet-500" },
  { key: "PLANNED", label: "Planned", dot: "bg-amber-500" },
  { key: "IN_PROGRESS", label: "In Progress", dot: "bg-blue-600" },
  { key: "COMPLETED", label: "Completed", dot: "bg-emerald-500" },
];

export function KanbanBoardPage() {
  const { hasRole } = useAuth();
  const { showToast } = useToast();
  const isPMOrAdmin = hasRole("ADMIN", "PRODUCT_MANAGER");

  const [insights, setInsights] = useState<InsightGroup[]>([]);
  const [staff, setStaff] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [draggedId, setDraggedId] = useState<number | null>(null);

  const [activeCard, setActiveCard] = useState<InsightGroup | null>(null);
  const [drawerComments, setDrawerComments] = useState<CommentItem[]>([]);
  const [drawerActivity, setDrawerActivity] = useState<ActivityLogItem[]>([]);
  const [commentInput, setCommentInput] = useState("");
  const [dueDateInput, setDueDateInput] = useState("");
  const [assigneeInput, setAssigneeInput] = useState("");

  const loadBoard = async () => {
    setLoading(true);
    try {
      const [insRes, userRes] = await Promise.all([
        api.get<{ results: InsightGroup[] }>("/insights/?exclude_rejected=true&page_size=100"),
        api.get<{ results: User[] }>("/users/?internal_only=true&page_size=100"),
      ]);
      setInsights(insRes.data.results || []);
      setStaff(userRes.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải bảng Kanban."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBoard();
  }, []);

  const openDrawer = async (card: InsightGroup) => {
    setActiveCard(card);
    setDueDateInput(card.due_date || "");
    setAssigneeInput(card.assigned_to ? String(card.assigned_to) : "");
    try {
      const [cRes, aRes] = await Promise.all([
        api.get<CommentItem[]>(`/insights/${card.id}/comments/`),
        api.get<ActivityLogItem[]>(`/insights/${card.id}/activity/`),
      ]);
      setDrawerComments(cRes.data);
      setDrawerActivity(aRes.data);
    } catch {
      setDrawerComments([]);
      setDrawerActivity([]);
    }
  };

  const moveCard = async (cardId: number, targetStatus: InsightStatus) => {
    const previous = insights;
    setInsights((prev) =>
      prev.map((item) => (item.id === cardId ? { ...item, status: targetStatus } : item))
    );
    try {
      const res = await api.post<InsightGroup>(`/insights/${cardId}/move_kanban/`, {
        status: targetStatus,
      });
      setInsights((prev) => prev.map((item) => (item.id === cardId ? res.data : item)));
      if (activeCard?.id === cardId) setActiveCard(res.data);
      showToast(`Đã chuyển ${res.data.code} sang ${targetStatus}`, "success");
    } catch (err) {
      setInsights(previous);
      showToast(getApiErrorMessage(err, "Bạn không có quyền di chuyển card này."), "error");
    }
  };

  const saveDrawerMeta = async () => {
    if (!activeCard) return;
    try {
      const res = await api.post<InsightGroup>(`/insights/${activeCard.id}/move_kanban/`, {
        status: activeCard.status,
        assigned_to: assigneeInput ? Number(assigneeInput) : null,
        due_date: dueDateInput || null,
      });
      setActiveCard(res.data);
      setInsights((prev) => prev.map((x) => (x.id === res.data.id ? res.data : x)));
      showToast("Đã cập nhật phân công & deadline.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const postDrawerComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCard || !commentInput.trim()) return;
    try {
      const res = await api.post<CommentItem>(`/insights/${activeCard.id}/comments/`, {
        content: commentInput,
      });
      setDrawerComments((prev) => [...prev, res.data]);
      setCommentInput("");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title="Kanban Board"
      subtitle="Kéo thả Insight giữa 5 giai đoạn Product Discovery & theo dõi tiến độ thực hiện"
    >
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {COLUMNS.map((c) => (
            <div key={c.key} className="h-96 rounded-2xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4 items-start">
          {COLUMNS.map((col) => {
            const colCards = insights.filter((i) => i.status === col.key);
            return (
              <div
                key={col.key}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (draggedId !== null) {
                    moveCard(draggedId, col.key);
                    setDraggedId(null);
                  }
                }}
                className="bg-slate-100/80 rounded-2xl border border-slate-200 p-3 min-h-[460px] flex flex-col gap-3"
              >
                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${col.dot}`} />
                    <span className="font-bold text-sm text-slate-800">{col.label}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full bg-white text-xs font-bold text-slate-600 border border-slate-200">
                    {colCards.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {colCards.map((card) => (
                    <div
                      key={card.id}
                      draggable
                      onDragStart={() => setDraggedId(card.id)}
                      onClick={() => openDrawer(card)}
                      className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-sm hover:border-brand-400 cursor-grab active:cursor-grabbing transition-all"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="text-[11px] font-mono font-bold text-brand-600">{card.code}</span>
                        <PriorityBadge level={card.priority_level} score={card.priority_score} />
                      </div>
                      <div className="font-semibold text-sm text-slate-900 line-clamp-2 mb-2">
                        {card.title}
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span className="inline-flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          {card.feedback_count} fb · {card.affected_customers_count} kh
                        </span>
                        {card.due_date && (
                          <span className="inline-flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {card.due_date}
                          </span>
                        )}
                      </div>
                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
                        <span className="text-[11px] font-medium text-slate-600 truncate">
                          {card.assigned_to_detail?.display_name || "Chưa gán"}
                        </span>
                        <select
                          value={card.status}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => moveCard(card.id, e.target.value as InsightStatus)}
                          className="text-[11px] px-1.5 py-0.5 rounded border border-slate-200 bg-slate-50"
                        >
                          {COLUMNS.map((opt) => (
                            <option key={opt.key} value={opt.key}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Slide-over Card Detail Drawer */}
      {activeCard && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-lg h-full overflow-y-auto p-6 shadow-2xl flex flex-col gap-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono font-bold text-brand-600">{activeCard.code}</span>
                  <PriorityBadge level={activeCard.priority_level} score={activeCard.priority_score} />
                </div>
                <h3 className="text-lg font-bold text-slate-900">{activeCard.title}</h3>
              </div>
              <button
                onClick={() => setActiveCard(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-slate-600">{activeCard.description}</p>

            <div className="grid grid-cols-2 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Cột trạng thái</label>
                <select
                  value={activeCard.status}
                  onChange={(e) => moveCard(activeCard.id, e.target.value as InsightStatus)}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  {COLUMNS.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Deadline</label>
                <input
                  type="date"
                  disabled={!isPMOrAdmin}
                  value={dueDateInput}
                  onChange={(e) => setDueDateInput(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-sm bg-white"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Người phụ trách</label>
                <select
                  disabled={!isPMOrAdmin}
                  value={assigneeInput}
                  onChange={(e) => setAssigneeInput(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="">-- Chưa gán --</option>
                  {staff.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name} ({u.role_name})
                    </option>
                  ))}
                </select>
              </div>
              {isPMOrAdmin && (
                <div className="col-span-2 flex justify-between items-center pt-1">
                  <Link
                    to={`/insights/${activeCard.id}`}
                    className="text-xs font-semibold text-brand-600 hover:underline"
                  >
                    Mở trang chi tiết Insight →
                  </Link>
                  <button
                    onClick={saveDrawerMeta}
                    className="px-3.5 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold"
                  >
                    Lưu phân công & hạn
                  </button>
                </div>
              )}
            </div>

            <div>
              <h4 className="font-bold text-sm text-slate-900 mb-2 flex items-center gap-1.5">
                <MessageSquare className="w-4 h-4 text-brand-600" />
                Bình luận nội bộ ({drawerComments.length})
              </h4>
              <div className="space-y-2 mb-3 max-h-44 overflow-y-auto">
                {drawerComments.map((c) => (
                  <div key={c.id} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                    <div className="font-bold text-slate-800">{c.author.display_name}</div>
                    <div className="text-slate-600 mt-0.5">{c.content}</div>
                  </div>
                ))}
              </div>
              <form onSubmit={postDrawerComment} className="flex gap-2">
                <input
                  type="text"
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                  placeholder="Thêm bình luận nội bộ..."
                  className="flex-1 px-3 py-1.5 rounded-lg border border-slate-300 text-sm"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </div>

            <div>
              <h4 className="font-bold text-sm text-slate-900 mb-2">Lịch sử thay đổi</h4>
              <div className="space-y-2">
                {drawerActivity.map((a) => (
                  <div key={a.id} className="text-xs border-l-2 border-slate-300 pl-2.5 text-slate-600">
                    <div>{a.description}</div>
                    <div className="text-slate-400 text-[11px]">
                      {new Date(a.created_at).toLocaleString("vi-VN")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
