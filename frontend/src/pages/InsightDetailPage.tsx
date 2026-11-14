import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Copy,
  GitMerge,
  Map,
  RefreshCw,
  Scissors,
  Send,
  Sliders,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, SourceBadge, StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ActivityLogItem, CommentItem, InsightGroup, User } from "../types";

export function InsightDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const { showToast } = useToast();
  const canManage = hasRole("ADMIN", "PRODUCT_MANAGER");

  const [insight, setInsight] = useState<InsightGroup | null>(null);
  const [allInsights, setAllInsights] = useState<InsightGroup[]>([]);
  const [staff, setStaff] = useState<User[]>([]);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [activities, setActivities] = useState<ActivityLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [commentText, setCommentText] = useState("");
  const [replyTone, setReplyTone] = useState<"empathetic" | "update" | "resolved">("empathetic");
  const [regenLoading, setRegenLoading] = useState(false);

  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState(80);
  const [overrideNotes, setOverrideNotes] = useState("");

  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeSourceId, setMergeSourceId] = useState("");

  const [splitIds, setSplitIds] = useState<number[]>([]);
  const [splitOpen, setSplitOpen] = useState(false);
  const [splitTitle, setSplitTitle] = useState("");

  const [roadmapOpen, setRoadmapOpen] = useState(false);
  const [roadmapForm, setRoadmapForm] = useState({
    title: "",
    description: "",
    public_description: "",
    internal_notes: "",
    status: "PLANNED",
    visibility: "PUBLIC",
    quarter: "Q1 2027",
    progress_percent: 10,
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [insRes, cmtRes, actRes, listRes, userRes] = await Promise.all([
        api.get<InsightGroup>(`/insights/${id}/`),
        api.get<CommentItem[]>(`/insights/${id}/comments/`),
        api.get<ActivityLogItem[]>(`/insights/${id}/activity/`),
        api.get<{ results: InsightGroup[] }>("/insights/?page_size=100"),
        api.get<{ results: User[] }>("/users/?internal_only=true&page_size=100"),
      ]);
      const ins = insRes.data;
      setInsight(ins);
      setOverrideScore(ins.priority_score);
      setOverrideNotes(ins.pm_priority_notes || "");
      setRoadmapForm((prev) => ({
        ...prev,
        title: ins.title,
        description: ins.description,
        public_description: ins.description,
      }));
      setComments(cmtRes.data);
      setActivities(actRes.data);
      setAllInsights((listRes.data.results || []).filter((x) => x.id !== ins.id));
      setStaff(userRes.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải chi tiết Insight."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleConfirm = async () => {
    if (!insight) return;
    await api.post(`/insights/${insight.id}/confirm/`, {});
    showToast("Đã xác nhận nhóm Insight.", "success");
    loadData();
  };

  const handleReject = async () => {
    if (!insight) return;
    await api.post(`/insights/${insight.id}/reject/`, {});
    showToast("Đã từ chối nhóm Insight.", "info");
    loadData();
  };

  const handleMoveStatus = async (newStatus: string, assigned_to?: string) => {
    if (!insight) return;
    try {
      const res = await api.post<InsightGroup>(`/insights/${insight.id}/move_kanban/`, {
        status: newStatus,
        ...(assigned_to !== undefined ? { assigned_to: assigned_to ? Number(assigned_to) : null } : {}),
      });
      setInsight(res.data);
      showToast("Đã cập nhật Kanban & phân công.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleOverridePriority = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insight) return;
    try {
      const res = await api.post<InsightGroup>(`/insights/${insight.id}/override_priority/`, {
        priority_score: overrideScore,
        pm_priority_notes: overrideNotes,
      });
      setInsight(res.data);
      setOverrideOpen(false);
      showToast("Đã cập nhật điểm ưu tiên theo PM.", "success");
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleRegenerateReply = async () => {
    if (!insight) return;
    setRegenLoading(true);
    try {
      const res = await api.post<{ draft_customer_reply: string }>(
        `/insights/${insight.id}/regenerate_reply/`,
        { tone: replyTone, use_llm: true }
      );
      setInsight({ ...insight, draft_customer_reply: res.data.draft_customer_reply });
      showToast("Đã tạo nháp phản hồi mới!", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setRegenLoading(false);
    }
  };

  const handleMerge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insight || !mergeSourceId) return;
    try {
      await api.post(`/insights/${insight.id}/merge/`, {
        source_insight_id: Number(mergeSourceId),
      });
      showToast("Đã gộp nhóm insight thành công!", "success");
      setMergeOpen(false);
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleSplit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insight || splitIds.length === 0) return;
    try {
      const res = await api.post<{ new_insight: InsightGroup }>(`/insights/${insight.id}/split/`, {
        feedback_ids: splitIds,
        new_title: splitTitle,
      });
      showToast(`Đã tách sang nhóm mới ${res.data.new_insight.code}!`, "success");
      setSplitOpen(false);
      setSplitIds([]);
      setSplitTitle("");
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleRemoveFeedback = async (feedbackId: number) => {
    if (!insight) return;
    try {
      await api.post(`/insights/${insight.id}/remove_feedback/`, { feedback_id: feedbackId });
      showToast("Đã gỡ feedback khỏi nhóm.", "info");
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handlePromoteRoadmap = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insight) return;
    try {
      await api.post("/roadmap/", {
        ...roadmapForm,
        product: insight.product,
        owner: insight.assigned_to,
        insight_group_ids: [insight.id],
      });
      showToast("Đã tạo Roadmap Item từ Insight!", "success");
      setRoadmapOpen(false);
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handlePostComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insight || !commentText.trim()) return;
    const res = await api.post<CommentItem>(`/insights/${insight.id}/comments/`, {
      content: commentText,
    });
    setComments([...comments, res.data]);
    setCommentText("");
  };

  if (loading || !insight) {
    return (
      <AppLayout title="Chi tiết Insight">
        <div className="h-64 rounded-2xl bg-white border border-slate-200 animate-pulse" />
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title={`${insight.code} — ${insight.title}`}
      subtitle={`Sản phẩm: ${insight.product_name} · Phân tích bởi: ${insight.analysis_mode}`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => navigate("/insights")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Danh sách
          </button>
          {canManage && (
            <>
              {insight.verification_status !== "CONFIRMED" && (
                <button
                  onClick={handleConfirm}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
                >
                  <Check className="w-4 h-4" />
                  Xác nhận nhóm
                </button>
              )}
              {insight.verification_status !== "REJECTED" && (
                <button
                  onClick={handleReject}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-200 text-rose-700 bg-white text-sm font-semibold hover:bg-rose-50"
                >
                  <X className="w-4 h-4" />
                  Từ chối
                </button>
              )}
              <button
                onClick={() => setMergeOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm font-medium hover:bg-slate-50"
              >
                <GitMerge className="w-4 h-4" />
                Gộp nhóm
              </button>
              <button
                onClick={() => setRoadmapOpen(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
              >
                <Map className="w-4 h-4" />
                Đưa lên Roadmap
              </button>
            </>
          )}
        </div>
      }
    >
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left Main Column */}
        <div className="lg:col-span-2 space-y-6">
          {/* AI Summary Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={insight.verification_status} />
              <StatusBadge status={insight.status} />
              <PriorityBadge level={insight.priority_level} score={insight.priority_score} />
              <span className="text-xs text-slate-500 ml-auto">
                Độ tin cậy AI: {(insight.ai_confidence * 100).toFixed(0)}%
              </span>
            </div>

            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                Tóm tắt vấn đề (AI Summarization)
              </h3>
              <p className="text-slate-800 leading-relaxed text-sm">{insight.description}</p>
            </div>

            <div className="grid md:grid-cols-2 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200">
                <h4 className="text-xs font-bold uppercase text-amber-900 mb-2">
                  Nguyên nhân có thể xảy ra (Giả thuyết cần kiểm tra)
                </h4>
                <ul className="space-y-1.5 text-xs text-amber-950 list-disc pl-4">
                  {(insight.possible_causes || []).map((c, idx) => (
                    <li key={idx}>{c}</li>
                  ))}
                </ul>
              </div>
              <div className="p-4 rounded-xl bg-indigo-50/70 border border-indigo-200">
                <h4 className="text-xs font-bold uppercase text-indigo-900 mb-2">
                  Đề xuất hướng cải tiến sản phẩm
                </h4>
                <ul className="space-y-1.5 text-xs text-indigo-950 list-disc pl-4">
                  {(insight.ai_recommendations || []).map((r, idx) => (
                    <li key={idx}>{r}</li>
                  ))}
                </ul>
              </div>
            </div>

            {insight.user_impact && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700">
                <strong className="text-slate-900">Ảnh hưởng tới người dùng: </strong>
                {insight.user_impact}
              </div>
            )}
          </div>

          {/* AI Draft Customer Reply */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="font-bold text-slate-900 flex items-center gap-2 text-sm">
                  <Sparkles className="w-4 h-4 text-brand-600" />
                  AI Nháp phản hồi khách hàng
                </h3>
                <p className="text-xs text-slate-500">
                  Sinh thư phản hồi chuẩn hóa để đội CSKH/PM xem xét trước khi gửi
                </p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={replyTone}
                  onChange={(e) => setReplyTone(e.target.value as typeof replyTone)}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
                >
                  <option value="empathetic">Đồng cảm & Tiếp nhận</option>
                  <option value="update">Cập nhật Roadmap</option>
                  <option value="resolved">Đã khắc phục xong</option>
                </select>
                <button
                  onClick={handleRegenerateReply}
                  disabled={regenLoading}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 disabled:opacity-60"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  {regenLoading ? "Đang tạo..." : "Tạo lại"}
                </button>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(insight.draft_customer_reply || "");
                    showToast("Đã sao chép nháp phản hồi!", "success");
                  }}
                  className="p-1.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50"
                  title="Sao chép"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-800 whitespace-pre-line font-normal">
              {insight.draft_customer_reply || "Chưa có nháp phản hồi."}
            </div>
          </div>

          {/* Member Feedbacks */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-900">
                Feedback thành viên ({insight.members?.length || 0})
              </h3>
              {canManage && splitIds.length > 0 && (
                <button
                  onClick={() => setSplitOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold"
                >
                  <Scissors className="w-3.5 h-3.5" />
                  Tách {splitIds.length} feedback sang nhóm mới
                </button>
              )}
            </div>

            <div className="space-y-2.5">
              {(insight.members || []).map((m) => (
                <div
                  key={m.feedback_id}
                  className="p-3.5 rounded-xl border border-slate-200 flex items-start justify-between gap-3"
                >
                  <div className="flex items-start gap-2.5 min-w-0">
                    {canManage && (
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={splitIds.includes(m.feedback_id)}
                        onChange={(e) =>
                          setSplitIds((prev) =>
                            e.target.checked
                              ? [...prev, m.feedback_id]
                              : prev.filter((x) => x !== m.feedback_id)
                          )
                        }
                      />
                    )}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="text-xs font-mono font-bold text-brand-600">{m.code}</span>
                        <SourceBadge code={m.source_code} />
                        {typeof m.similarity_to_centroid === "number" && (
                          <span className="text-[11px] text-slate-500">
                            Cosine tâm cụm: {(m.similarity_to_centroid * 100).toFixed(1)}%
                          </span>
                        )}
                      </div>
                      <Link to={`/inbox/${m.feedback_id}`} className="font-semibold text-sm text-slate-900 hover:underline">
                        {m.title}
                      </Link>
                      <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">{m.content}</p>
                    </div>
                  </div>
                  {canManage && (
                    <button
                      onClick={() => handleRemoveFeedback(m.feedback_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 shrink-0"
                      title="Gỡ khỏi nhóm"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Internal Comments */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="font-bold text-slate-900 mb-3">Thảo luận nội bộ ({comments.length})</h3>
            <div className="space-y-2.5 mb-4">
              {comments.map((c) => (
                <div key={c.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-sm">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-bold text-slate-900">
                      {c.author.display_name} ({c.author.role_name})
                    </span>
                    <span className="text-slate-400">{new Date(c.created_at).toLocaleString("vi-VN")}</span>
                  </div>
                  <p className="text-slate-700">{c.content}</p>
                </div>
              ))}
            </div>
            <form onSubmit={handlePostComment} className="flex gap-2">
              <input
                type="text"
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Ghi chú nội bộ cho đội ngũ Product / Dev / CS..."
                className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <button
                type="submit"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-xs font-semibold"
              >
                <Send className="w-3.5 h-3.5" />
                Gửi
              </button>
            </form>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          {/* Priority Breakdown */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900 text-sm">Điểm ưu tiên (0.4V + 0.35I + 0.25S)</h3>
              {canManage && (
                <button
                  onClick={() => setOverrideOpen(true)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:underline"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  Điều chỉnh
                </button>
              )}
            </div>

            <div className="space-y-3">
              {[
                { label: "V — Volume (40%)", score: insight.volume_score, color: "bg-indigo-600" },
                { label: "I — Impact (35%)", score: insight.impact_score, color: "bg-amber-500" },
                { label: "S — Severity (25%)", score: insight.severity_score, color: "bg-rose-500" },
              ].map((bar) => (
                <div key={bar.label}>
                  <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                    <span>{bar.label}</span>
                    <span>{bar.score}/100</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${bar.color}`}
                      style={{ width: `${Math.min(100, bar.score)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed">
              {insight.priority_reasoning}
              {insight.is_priority_overridden && (
                <div className="mt-2 pt-2 border-t border-slate-200 text-amber-800 font-medium">
                  PM đã điều chỉnh: {insight.pm_priority_notes || "Ghi đè thủ công"}
                </div>
              )}
            </div>
          </div>

          {/* Workflow Assignment */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-3">
            <h3 className="font-bold text-slate-900 text-sm">Quản lý Kanban & Phụ trách</h3>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Cột Kanban</label>
              <select
                value={insight.status}
                onChange={(e) => handleMoveStatus(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              >
                <option value="NEW">New</option>
                <option value="ANALYZING">Analyzing</option>
                <option value="PLANNED">Planned</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="COMPLETED">Completed</option>
              </select>
            </div>
            {canManage && (
              <div>
                <label className="block text-xs text-slate-500 mb-1">Người phụ trách</label>
                <select
                  value={insight.assigned_to || ""}
                  onChange={(e) => handleMoveStatus(insight.status, e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="">-- Chưa phân công --</option>
                  {staff.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name} ({u.role_name})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Activity History */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <h3 className="font-bold text-slate-900 text-sm mb-3">Lịch sử thay đổi</h3>
            <div className="space-y-3">
              {activities.length === 0 ? (
                <p className="text-xs text-slate-400">Chưa có nhật ký.</p>
              ) : (
                activities.map((a) => (
                  <div key={a.id} className="text-xs border-l-2 border-brand-300 pl-3">
                    <div className="font-medium text-slate-800">{a.description}</div>
                    <div className="text-slate-400 mt-0.5">
                      {a.actor?.display_name || "Hệ thống"} · {new Date(a.created_at).toLocaleString("vi-VN")}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Override Modal */}
      {overrideOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="font-bold text-lg text-slate-900 mb-3">Điều chỉnh điểm ưu tiên (PM Override)</h3>
            <form onSubmit={handleOverridePriority} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Điểm ưu tiên mới (0–100): <strong>{overrideScore}</strong>
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={0.5}
                  value={overrideScore}
                  onChange={(e) => setOverrideScore(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Lý do điều chỉnh</label>
                <textarea
                  rows={3}
                  required
                  value={overrideNotes}
                  onChange={(e) => setOverrideNotes(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setOverrideOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold">
                  Lưu điểm ưu tiên
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Merge Modal */}
      {mergeOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="font-bold text-lg text-slate-900 mb-3">Gộp nhóm Insight vào {insight.code}</h3>
            <form onSubmit={handleMerge} className="space-y-4">
              <select
                required
                value={mergeSourceId}
                onChange={(e) => setMergeSourceId(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              >
                <option value="">-- Chọn nhóm nguồn để gộp --</option>
                {allInsights.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.code}: {x.title} ({x.feedback_count} feedback)
                  </option>
                ))}
              </select>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setMergeOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold">
                  Gộp ngay
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Split Modal */}
      {splitOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="font-bold text-lg text-slate-900 mb-3">Tách {splitIds.length} feedback sang nhóm mới</h3>
            <form onSubmit={handleSplit} className="space-y-4">
              <input
                type="text"
                required
                value={splitTitle}
                onChange={(e) => setSplitTitle(e.target.value)}
                placeholder="Tiêu đề nhóm Insight mới"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setSplitOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold">
                  Xác nhận tách
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Promote to Roadmap Modal */}
      {roadmapOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl">
            <h3 className="font-bold text-lg text-slate-900 mb-3">Tạo hạng mục Product Roadmap từ {insight.code}</h3>
            <form onSubmit={handlePromoteRoadmap} className="space-y-3">
              <input
                type="text"
                required
                value={roadmapForm.title}
                onChange={(e) => setRoadmapForm({ ...roadmapForm, title: e.target.value })}
                placeholder="Tên tính năng / cải tiến"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={3}
                required
                value={roadmapForm.description}
                onChange={(e) => setRoadmapForm({ ...roadmapForm, description: e.target.value })}
                placeholder="Mô tả nội bộ"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={2}
                value={roadmapForm.public_description}
                onChange={(e) => setRoadmapForm({ ...roadmapForm, public_description: e.target.value })}
                placeholder="Mô tả hiển thị trên Public Roadmap (ẩn thông tin nội bộ)"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <div className="grid grid-cols-3 gap-2">
                <select
                  value={roadmapForm.status}
                  onChange={(e) => setRoadmapForm({ ...roadmapForm, status: e.target.value })}
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="PLANNED">Planned</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="COMPLETED">Completed</option>
                </select>
                <select
                  value={roadmapForm.visibility}
                  onChange={(e) => setRoadmapForm({ ...roadmapForm, visibility: e.target.value })}
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="PUBLIC">Public</option>
                  <option value="PRIVATE">Private</option>
                </select>
                <input
                  type="text"
                  value={roadmapForm.quarter}
                  onChange={(e) => setRoadmapForm({ ...roadmapForm, quarter: e.target.value })}
                  placeholder="Q1 2027"
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setRoadmapOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold">
                  Tạo Roadmap Item
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
