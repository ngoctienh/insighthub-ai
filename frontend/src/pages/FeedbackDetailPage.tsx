import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Copy,
  Send,
  Sparkles,
  Tag as TagIcon,
  ThumbsUp,
  UserCheck,
} from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, SourceBadge, StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ActivityLogItem, CommentItem, Feedback, Tag, User } from "../types";

interface SimilarMatch {
  feedback_id: number;
  code: string;
  title: string;
  similarity_score: number;
  is_exact_normalized_match: boolean;
}

export function FeedbackDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isInternal, hasRole } = useAuth();
  const { showToast } = useToast();

  const [fb, setFb] = useState<Feedback | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [activities, setActivities] = useState<ActivityLogItem[]>([]);
  const [similarMatches, setSimilarMatches] = useState<SimilarMatch[]>([]);
  const [simLoading, setSimLoading] = useState(false);

  const [staff, setStaff] = useState<User[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [commentText, setCommentText] = useState("");
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [fbRes, cmtRes] = await Promise.all([
        api.get<Feedback>(`/feedbacks/${id}/`),
        api.get<CommentItem[]>(`/feedbacks/${id}/comments/`),
      ]);
      setFb(fbRes.data);
      setComments(cmtRes.data);

      if (isInternal) {
        api.get<ActivityLogItem[]>(`/feedbacks/${id}/activity/`).then((r) => setActivities(r.data)).catch(() => {});
        api.get<{ results: User[] }>("/users/?internal_only=true&page_size=100")
          .then((r) => setStaff(r.data.results || []))
          .catch(() => {});
        api.get<Tag[]>("/tags/").then((r) => setAllTags(r.data)).catch(() => {});
      }
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải chi tiết feedback."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleStatusChange = async (newStatus: string) => {
    if (!fb) return;
    try {
      const res = await api.patch<Feedback>(`/feedbacks/${fb.id}/`, { status: newStatus });
      setFb(res.data);
      showToast("Đã cập nhật trạng thái.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleAssign = async (userId: string) => {
    if (!fb) return;
    try {
      const res = await api.post<Feedback>(`/feedbacks/${fb.id}/assign/`, {
        assigned_to: userId ? Number(userId) : null,
      });
      setFb(res.data);
      showToast("Đã cập nhật người phụ trách.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleToggleTag = async (tagId: number) => {
    if (!fb) return;
    const current = fb.tags.map((t) => t.id);
    const next = current.includes(tagId) ? current.filter((x) => x !== tagId) : [...current, tagId];
    try {
      const res = await api.post<Feedback>(`/feedbacks/${fb.id}/tags/`, { tag_ids: next });
      setFb(res.data);
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleFindSimilar = async () => {
    if (!fb) return;
    setSimLoading(true);
    try {
      const res = await api.get<{ matches: SimilarMatch[] }>(`/feedbacks/${fb.id}/similar/?min_similarity=0.3`);
      setSimilarMatches(res.data.matches);
      if (res.data.matches.length === 0) {
        showToast("Không tìm thấy feedback tương đồng vượt ngưỡng.", "info");
      }
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể kết nối AI Service."), "error");
    } finally {
      setSimLoading(false);
    }
  };

  const handleMarkDuplicate = async (targetId: number, simScore?: number) => {
    if (!fb) return;
    try {
      const res = await api.post<Feedback>(`/feedbacks/${fb.id}/mark_duplicate/`, {
        duplicate_of_id: targetId,
        similarity_score: simScore,
        confirm: true,
      });
      setFb(res.data);
      showToast("Đã xác nhận đánh dấu trùng lặp.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleUnmarkDuplicate = async () => {
    if (!fb) return;
    try {
      const res = await api.post<Feedback>(`/feedbacks/${fb.id}/unmark_duplicate/`, {});
      setFb(res.data);
      showToast("Đã gỡ đánh dấu trùng lặp.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handlePostComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fb || !commentText.trim()) return;
    try {
      const res = await api.post<CommentItem>(`/feedbacks/${fb.id}/comments/`, {
        content: commentText,
        is_internal: isInternal ? isInternalNote : false,
      });
      setComments((prev) => [...prev, res.data]);
      setCommentText("");
      showToast("Đã gửi bình luận.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleVote = async () => {
    if (!fb) return;
    const res = await api.post<{ voted: boolean; votes_count: number }>(`/feedbacks/${fb.id}/vote/`);
    setFb({ ...fb, user_has_voted: res.data.voted, votes_count: res.data.votes_count });
  };

  if (loading || !fb) {
    return (
      <AppLayout title="Chi tiết Feedback">
        <div className="h-64 bg-white rounded-2xl border border-slate-200 animate-pulse" />
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title={`${fb.code} — ${fb.title}`}
      subtitle={`Sản phẩm: ${fb.product_name} · Gửi lúc ${new Date(fb.submitted_at).toLocaleString("vi-VN")}`}
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Quay lại
          </button>
          <button
            onClick={handleVote}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-semibold ${
              fb.user_has_voted ? "bg-brand-50 border-brand-300 text-brand-700" : "bg-white border-slate-300 text-slate-700"
            }`}
          >
            <ThumbsUp className="w-4 h-4" />
            Vote ({fb.votes_count})
          </button>
        </div>
      }
    >
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Column */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <SourceBadge code={fb.source_code} />
              <StatusBadge status={fb.status} />
              <PriorityBadge level={fb.impact_level} score={fb.priority_score} />
              {fb.is_duplicate_confirmed && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-zinc-100 border border-zinc-300 text-xs font-semibold text-zinc-700">
                  <Copy className="w-3 h-3" />
                  Đã xác nhận trùng lặp
                </span>
              )}
            </div>

            <p className="text-slate-800 whitespace-pre-line leading-relaxed text-[15px]">
              {fb.content}
            </p>

            {fb.duplicate_of_detail && (
              <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-between text-xs">
                <div>
                  Liên kết trùng lặp với{" "}
                  <Link to={`/inbox/${fb.duplicate_of_detail.id}`} className="font-bold text-amber-900 underline">
                    {fb.duplicate_of_detail.code}: {fb.duplicate_of_detail.title}
                  </Link>
                  {fb.similarity_score && ` (Cosine = ${(fb.similarity_score * 100).toFixed(1)}%)`}
                </div>
                {isInternal && (
                  <button
                    onClick={handleUnmarkDuplicate}
                    className="px-2.5 py-1 rounded bg-white border border-amber-300 font-medium text-amber-900"
                  >
                    Gỡ trùng lặp
                  </button>
                )}
              </div>
            )}

            {fb.source_metadata && Object.keys(fb.source_metadata).length > 0 && (
              <div className="mt-5 pt-4 border-t border-slate-100">
                <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Metadata từ nguồn tiếp nhận</div>
                <pre className="text-xs bg-slate-50 p-3 rounded-xl border border-slate-200 overflow-x-auto text-slate-700">
                  {JSON.stringify(fb.source_metadata, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* AI Similarity Search */}
          {isInternal && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-slate-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-brand-600" />
                    Kiểm tra Feedback tương tự (AI Cosine Similarity)
                  </h2>
                  <p className="text-xs text-slate-500">
                    So sánh vector để phát hiện các phản hồi gần giống trước khi xác nhận trùng lặp
                  </p>
                </div>
                <button
                  onClick={handleFindSimilar}
                  disabled={simLoading}
                  className="px-3.5 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold hover:bg-brand-700 disabled:opacity-60"
                >
                  {simLoading ? "Đang tính Cosine..." : "Quét tương đồng AI"}
                </button>
              </div>

              {similarMatches.length > 0 && (
                <div className="space-y-2">
                  {similarMatches.map((m) => (
                    <div
                      key={m.feedback_id}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl border border-slate-200 bg-slate-50"
                    >
                      <div>
                        <Link to={`/inbox/${m.feedback_id}`} className="text-sm font-semibold text-slate-900 hover:text-brand-600">
                          {m.code}: {m.title}
                        </Link>
                        <div className="text-xs text-slate-500 mt-0.5">
                          Cosine Similarity: <strong>{(m.similarity_score * 100).toFixed(1)}%</strong>
                          {m.is_exact_normalized_match && " · Trùng khớp văn bản chuẩn hóa"}
                        </div>
                      </div>
                      {hasRole("ADMIN", "PRODUCT_MANAGER", "CUSTOMER_SUPPORT") && (
                        <button
                          onClick={() => handleMarkDuplicate(m.feedback_id, m.similarity_score)}
                          className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs font-medium hover:bg-slate-100 shrink-0"
                        >
                          Xác nhận trùng lặp
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Comments */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h2 className="font-bold text-slate-900 mb-4">Trao đổi & Ghi chú ({comments.length})</h2>
            <div className="space-y-3 mb-5">
              {comments.length === 0 ? (
                <p className="text-sm text-slate-400">Chưa có bình luận nào.</p>
              ) : (
                comments.map((c) => (
                  <div
                    key={c.id}
                    className={`p-3.5 rounded-xl border ${
                      c.is_internal ? "bg-amber-50/70 border-amber-200" : "bg-slate-50 border-slate-200"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900">{c.author.display_name}</span>
                        <span className="text-[11px] text-slate-500">{c.author.role_name}</span>
                        {c.is_internal && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-200/70 text-amber-900 text-[10px] font-bold">
                            NỘI BỘ
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-400">
                        {new Date(c.created_at).toLocaleString("vi-VN")}
                      </span>
                    </div>
                    <p className="text-sm text-slate-800 whitespace-pre-line">{c.content}</p>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handlePostComment} className="space-y-3">
              <textarea
                rows={3}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder={
                  isInternal
                    ? "Nhập phản hồi cho khách hàng hoặc ghi chú nội bộ..."
                    : "Bổ sung thêm thông tin hoặc ảnh hưởng cho đội ngũ hỗ trợ..."
                }
                className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm outline-none focus:border-brand-500"
              />
              <div className="flex items-center justify-between">
                {isInternal ? (
                  <label className="inline-flex items-center gap-2 text-xs font-medium text-amber-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isInternalNote}
                      onChange={(e) => setIsInternalNote(e.target.checked)}
                    />
                    Chỉ hiển thị nội bộ (ẩn với Khách hàng)
                  </label>
                ) : (
                  <span />
                )}
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-xs font-semibold hover:bg-brand-700"
                >
                  <Send className="w-3.5 h-3.5" />
                  Gửi bình luận
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <h3 className="font-bold text-slate-900 text-sm">Thông tin xử lý</h3>
            <div>
              <div className="text-xs text-slate-500">Người gửi</div>
              <div className="text-sm font-semibold text-slate-900">{fb.sender_name}</div>
              <div className="text-xs text-slate-500">{fb.sender_email}</div>
            </div>

            {isInternal && (
              <>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Trạng thái xử lý</label>
                  <select
                    value={fb.status}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                  >
                    <option value="NEW">New</option>
                    <option value="TRIAGING">Triaging</option>
                    <option value="ANALYZING">Analyzing</option>
                    <option value="PLANNED">Planned</option>
                    <option value="IN_PROGRESS">In Progress</option>
                    <option value="COMPLETED">Completed</option>
                    <option value="CLOSED">Closed</option>
                    <option value="DUPLICATE">Duplicate</option>
                  </select>
                </div>

                {hasRole("ADMIN", "PRODUCT_MANAGER", "CUSTOMER_SUPPORT") && (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1 flex items-center gap-1">
                      <UserCheck className="w-3.5 h-3.5" />
                      Người phụ trách
                    </label>
                    <select
                      value={fb.assigned_to || ""}
                      onChange={(e) => handleAssign(e.target.value)}
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

                <div>
                  <label className="block text-xs text-slate-500 mb-1.5 flex items-center gap-1">
                    <TagIcon className="w-3.5 h-3.5" />
                    Nhãn phân loại
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {allTags.map((t) => {
                      const active = fb.tags.some((x) => x.id === t.id);
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => handleToggleTag(t.id)}
                          className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                            active
                              ? "bg-brand-600 text-white border-brand-600"
                              : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                          }`}
                        >
                          {t.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {fb.related_insights.length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-1.5">Nhóm Insight liên quan</div>
                <div className="space-y-1.5">
                  {fb.related_insights.map((ins) => (
                    <Link
                      key={ins.id}
                      to={isInternal ? `/insights/${ins.id}` : "#"}
                      className="block p-2.5 rounded-lg bg-indigo-50/60 border border-indigo-200 text-xs font-semibold text-indigo-900 hover:bg-indigo-50"
                    >
                      {ins.code} · {ins.title}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {isInternal && activities.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h3 className="font-bold text-slate-900 text-sm mb-3">Lịch sử thay đổi</h3>
              <div className="space-y-3">
                {activities.map((a) => (
                  <div key={a.id} className="text-xs border-l-2 border-brand-300 pl-3">
                    <div className="font-medium text-slate-800">{a.description}</div>
                    <div className="text-slate-400 mt-0.5">
                      {a.actor?.display_name || "Hệ thống"} · {new Date(a.created_at).toLocaleString("vi-VN")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
