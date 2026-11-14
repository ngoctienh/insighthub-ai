import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Filter,
  Plus,
  Search,
  ThumbsUp,
  Trash2,
  X,
} from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, SourceBadge, StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Feedback, Product, Tag, User } from "../types";

export function FeedbackInboxPage() {
  const { user, isInternal, hasRole } = useAuth();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [products, setProducts] = useState<Product[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [staff, setStaff] = useState<User[]>([]);

  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [impactFilter, setImpactFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [unclusteredOnly, setUnclusteredOnly] = useState(false);
  const [duplicateOnly, setDuplicateOnly] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newFb, setNewFb] = useState({
    product: "",
    source_code: "WEB_FORM",
    title: "",
    content: "",
    impact_level: "MEDIUM",
    sender_name: "",
    sender_email: "",
  });

  useEffect(() => {
    api.get<Product[]>("/products/").then((r) => {
      setProducts(r.data);
      if (r.data[0]) setNewFb((prev) => ({ ...prev, product: String(r.data[0].id) }));
    }).catch(() => {});
    api.get<Tag[]>("/tags/").then((r) => setTags(r.data)).catch(() => {});
    if (isInternal) {
      api.get<{ results: User[] }>("/users/?internal_only=true&page_size=100")
        .then((r) => setStaff(r.data.results || []))
        .catch(() => {});
    }
  }, [isInternal]);

  const loadFeedbacks = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ count: number; results: Feedback[] }>("/feedbacks/", {
        params: {
          page,
          search: search || undefined,
          status: statusFilter || undefined,
          source: sourceFilter || undefined,
          impact_level: impactFilter || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          unclustered_only: unclusteredOnly ? "true" : undefined,
          duplicate_only: duplicateOnly ? "true" : undefined,
        },
      });
      setFeedbacks(res.data.results);
      setTotalCount(res.data.count);
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải danh sách feedback."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFeedbacks();
  }, [page, statusFilter, sourceFilter, impactFilter, dateFrom, dateTo, unclusteredOnly, duplicateOnly]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    if (search.trim()) setSearchParams({ search: search.trim() });
    else setSearchParams({});
    loadFeedbacks();
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post("/feedbacks/", {
        ...newFb,
        product: Number(newFb.product),
      });
      showToast("Đã tạo feedback thành công!", "success");
      setCreateOpen(false);
      setNewFb((prev) => ({ ...prev, title: "", content: "", sender_name: "", sender_email: "" }));
      loadFeedbacks();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setCreating(false);
    }
  };

  const handleVote = async (id: number) => {
    try {
      const res = await api.post<{ voted: boolean; votes_count: number }>(`/feedbacks/${id}/vote/`);
      setFeedbacks((prev) =>
        prev.map((item) =>
          item.id === id
            ? { ...item, user_has_voted: res.data.voted, votes_count: res.data.votes_count }
            : item
        )
      );
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleDelete = async (fb: Feedback) => {
    if (!window.confirm(`Xác nhận xóa feedback ${fb.code}?`)) return;
    try {
      await api.delete(`/feedbacks/${fb.id}/`);
      showToast(`Đã xóa ${fb.code}`, "success");
      loadFeedbacks();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title={isInternal ? "Feedback Inbox" : "Phản hồi của tôi"}
      subtitle={`Tổng cộng ${totalCount} phản hồi được lưu trong PostgreSQL`}
      actions={
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
        >
          <Plus className="w-4 h-4" />
          Tạo Feedback
        </button>
      }
    >
      {/* Filters Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 mb-6 shadow-sm space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo mã (FB-0001), tiêu đề, nội dung, email..."
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
          >
            Tìm kiếm
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Filter className="w-4 h-4 text-slate-400 mr-1" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="NEW">New</option>
            <option value="TRIAGING">Triaging</option>
            <option value="ANALYZING">Analyzing</option>
            <option value="PLANNED">Planned</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="DUPLICATE">Duplicate</option>
          </select>

          <select
            value={sourceFilter}
            onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
          >
            <option value="">Tất cả nguồn</option>
            <option value="WEB_FORM">Website Form</option>
            <option value="EMAIL">Email</option>
            <option value="LIVE_CHAT">Live Chat</option>
            <option value="COMMUNITY">Community</option>
          </select>

          <select
            value={impactFilter}
            onChange={(e) => { setImpactFilter(e.target.value); setPage(1); }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
          >
            <option value="">Mức ảnh hưởng</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
            title="Từ ngày"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
            title="Đến ngày"
          />

          {isInternal && (
            <>
              <label className="inline-flex items-center gap-1.5 text-xs text-slate-700 px-2 py-1 rounded-lg bg-slate-50 border border-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={unclusteredOnly}
                  onChange={(e) => { setUnclusteredOnly(e.target.checked); setPage(1); }}
                />
                Chưa gom nhóm
              </label>
              <label className="inline-flex items-center gap-1.5 text-xs text-slate-700 px-2 py-1 rounded-lg bg-slate-50 border border-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={duplicateOnly}
                  onChange={(e) => { setDuplicateOnly(e.target.checked); setPage(1); }}
                />
                Nghi/Trùng lặp
              </label>
            </>
          )}
        </div>
      </div>

      {/* Table / List */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : feedbacks.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <p className="text-slate-700 font-semibold">Không tìm thấy phản hồi nào phù hợp bộ lọc</p>
          <p className="text-sm text-slate-500 mt-1">Thử bỏ bộ lọc hoặc tạo một feedback mới.</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Mã & Tiêu đề</th>
                  <th className="py-3 px-4">Nguồn</th>
                  <th className="py-3 px-4">Trạng thái</th>
                  <th className="py-3 px-4">Ảnh hưởng</th>
                  <th className="py-3 px-4">Insight liên quan</th>
                  <th className="py-3 px-4">Phụ trách</th>
                  <th className="py-3 px-4 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {feedbacks.map((fb) => (
                  <tr key={fb.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 max-w-md">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono font-semibold text-brand-600">{fb.code}</span>
                        <span className="text-xs text-slate-400">
                          {new Date(fb.submitted_at).toLocaleDateString("vi-VN")}
                        </span>
                        {fb.is_duplicate_confirmed && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-700">
                            DUPLICATE
                          </span>
                        )}
                      </div>
                      <Link
                        to={`/inbox/${fb.id}`}
                        className="font-semibold text-slate-900 hover:text-brand-600 line-clamp-1"
                      >
                        {fb.title}
                      </Link>
                      <div className="text-xs text-slate-500 mt-0.5 truncate">
                        {fb.sender_name} ({fb.sender_email})
                      </div>
                      {fb.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {fb.tags.map((tag) => (
                            <span
                              key={tag.id}
                              className="px-2 py-0.5 rounded text-[10px] font-medium border"
                              style={{
                                borderColor: `${tag.color}40`,
                                backgroundColor: `${tag.color}12`,
                                color: tag.color,
                              }}
                            >
                              {tag.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <SourceBadge code={fb.source_code} />
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <StatusBadge status={fb.status} />
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <PriorityBadge level={fb.impact_level} score={fb.priority_score} />
                    </td>
                    <td className="py-3.5 px-4 max-w-[200px]">
                      {fb.related_insights.length > 0 ? (
                        <Link
                          to={isInternal ? `/insights/${fb.related_insights[0].id}` : "#"}
                          className="text-xs font-medium text-brand-600 hover:underline line-clamp-2"
                        >
                          {fb.related_insights[0].code}: {fb.related_insights[0].title}
                        </Link>
                      ) : (
                        <span className="text-xs text-slate-400">Chưa gom nhóm</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap text-xs text-slate-600">
                      {fb.assigned_to_detail ? fb.assigned_to_detail.display_name : "—"}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() => handleVote(fb.id)}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-xs font-medium ${
                            fb.user_has_voted
                              ? "border-brand-300 bg-brand-50 text-brand-700"
                              : "border-slate-200 text-slate-600 hover:bg-slate-100"
                          }`}
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                          {fb.votes_count}
                        </button>
                        {(hasRole("ADMIN", "PRODUCT_MANAGER") ||
                          (user?.id === fb.author && fb.status === "NEW")) && (
                          <button
                            onClick={() => handleDelete(fb)}
                            className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                            title="Xóa feedback"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalCount > 20 && (
            <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
              <span>
                Trang {page} · Tổng {totalCount} phản hồi
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40"
                >
                  Trước
                </button>
                <button
                  disabled={page * 20 >= totalCount}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40"
                >
                  Sau
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Tạo Feedback mới</h3>
              <button onClick={() => setCreateOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Sản phẩm</label>
                  <select
                    value={newFb.product}
                    onChange={(e) => setNewFb({ ...newFb, product: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  >
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Mức ảnh hưởng</label>
                  <select
                    value={newFb.impact_level}
                    onChange={(e) => setNewFb({ ...newFb, impact_level: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </div>
              </div>

              {isInternal && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Tên người gửi</label>
                    <input
                      type="text"
                      value={newFb.sender_name}
                      onChange={(e) => setNewFb({ ...newFb, sender_name: e.target.value })}
                      placeholder={user?.display_name}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Email người gửi</label>
                    <input
                      type="email"
                      value={newFb.sender_email}
                      onChange={(e) => setNewFb({ ...newFb, sender_email: e.target.value })}
                      placeholder={user?.email}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tiêu đề</label>
                <input
                  type="text"
                  required
                  value={newFb.title}
                  onChange={(e) => setNewFb({ ...newFb, title: e.target.value })}
                  placeholder="Ví dụ: Không thể thanh toán bằng ví MoMo"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Nội dung chi tiết</label>
                <textarea
                  required
                  rows={4}
                  value={newFb.content}
                  onChange={(e) => setNewFb({ ...newFb, content: e.target.value })}
                  placeholder="Mô tả chi tiết ngữ cảnh gặp lỗi hoặc đề xuất cải tiến..."
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-60"
                >
                  {creating ? "Đang lưu..." : "Lưu Feedback"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
