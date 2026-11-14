import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Globe, Lock, Plus, Trash2, X } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { InsightGroup, Product, RoadmapItem, RoadmapVisibility, User } from "../types";

export function ProductRoadmapPage() {
  const { hasRole } = useAuth();
  const { showToast } = useToast();
  const canEdit = hasRole("ADMIN", "PRODUCT_MANAGER");

  const [items, setItems] = useState<RoadmapItem[]>([]);
  const [insights, setInsights] = useState<InsightGroup[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [staff, setStaff] = useState<User[]>([]);
  const [visibilityFilter, setVisibilityFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<RoadmapItem | null>(null);
  const [form, setForm] = useState({
    product: "",
    title: "",
    description: "",
    public_description: "",
    internal_notes: "",
    status: "PLANNED",
    visibility: "PUBLIC" as RoadmapVisibility,
    quarter: "Q1 2027",
    progress_percent: 0,
    owner: "",
    insight_group_ids: [] as number[],
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [rmRes, insRes, prodRes, userRes] = await Promise.all([
        api.get<RoadmapItem[]>("/roadmap/", {
          params: visibilityFilter ? { visibility: visibilityFilter } : {},
        }),
        api.get<{ results: InsightGroup[] }>("/insights/?page_size=100"),
        api.get<Product[]>("/products/"),
        api.get<{ results: User[] }>("/users/?internal_only=true&page_size=100"),
      ]);
      setItems(rmRes.data || []);
      setInsights(insRes.data.results || []);
      setProducts(prodRes.data || []);
      setStaff(userRes.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải Product Roadmap."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [visibilityFilter]);

  const openCreate = () => {
    setEditingItem(null);
    setForm({
      product: products[0] ? String(products[0].id) : "",
      title: "",
      description: "",
      public_description: "",
      internal_notes: "",
      status: "PLANNED",
      visibility: "PUBLIC",
      quarter: "Q1 2027",
      progress_percent: 10,
      owner: "",
      insight_group_ids: [],
    });
    setModalOpen(true);
  };

  const openEdit = (item: RoadmapItem) => {
    setEditingItem(item);
    setForm({
      product: String(item.product),
      title: item.title,
      description: item.description,
      public_description: item.public_description,
      internal_notes: item.internal_notes,
      status: item.status,
      visibility: item.visibility,
      quarter: item.quarter,
      progress_percent: item.progress_percent,
      owner: item.owner ? String(item.owner) : "",
      insight_group_ids: item.linked_insights.map((x) => x.id),
    });
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...form,
      product: Number(form.product),
      owner: form.owner ? Number(form.owner) : null,
    };
    try {
      if (editingItem) {
        await api.patch(`/roadmap/${editingItem.id}/`, payload);
        showToast("Đã cập nhật Roadmap item!", "success");
      } else {
        await api.post("/roadmap/", payload);
        showToast("Đã tạo Roadmap item mới!", "success");
      }
      setModalOpen(false);
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleDelete = async (item: RoadmapItem) => {
    if (!window.confirm(`Xóa hạng mục ${item.code}?`)) return;
    try {
      await api.delete(`/roadmap/${item.id}/`);
      showToast(`Đã xóa ${item.code}`, "info");
      loadData();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title="Product Roadmap (Nội bộ & Công khai)"
      subtitle="Liên kết Insight đã phát hiện vào lộ trình phát triển sản phẩm theo quý"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/public-roadmap"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium hover:bg-slate-50"
          >
            <Eye className="w-4 h-4" />
            Xem bản Public
          </Link>
          {canEdit && (
            <button
              onClick={openCreate}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
            >
              <Plus className="w-4 h-4" />
              Thêm Roadmap Item
            </button>
          )}
        </div>
      }
    >
      <div className="flex gap-2 mb-6">
        {[
          { val: "", label: "Tất cả (Public & Private)" },
          { val: "PUBLIC", label: "Public" },
          { val: "PRIVATE", label: "Private (Nội bộ)" },
        ].map((f) => (
          <button
            key={f.val}
            onClick={() => setVisibilityFilter(f.val)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold border ${
              visibilityFilter === f.val
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 rounded-2xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-500">
          Chưa có hạng mục roadmap nào.
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-5"
            >
              <div className="space-y-2 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-mono font-bold text-brand-600">{item.code}</span>
                  <StatusBadge status={item.status} />
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                      item.visibility === "PUBLIC"
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : "bg-slate-100 text-slate-700 border-slate-300"
                    }`}
                  >
                    {item.visibility === "PUBLIC" ? <Globe className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                    {item.visibility}
                  </span>
                  <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                    {item.quarter}
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
                <p className="text-sm text-slate-600">{item.description}</p>

                {item.internal_notes && (
                  <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
                    <strong>Ghi chú nội bộ (ẩn trên Public): </strong>
                    {item.internal_notes}
                  </div>
                )}

                {item.linked_insights.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {item.linked_insights.map((ins) => (
                      <Link
                        key={ins.id}
                        to={`/insights/${ins.id}`}
                        className="px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-xs font-medium text-indigo-800 hover:bg-indigo-100"
                      >
                        {ins.code}: {ins.title} ({ins.feedback_count} fb)
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              <div className="lg:w-64 shrink-0 space-y-3">
                <div>
                  <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                    <span>Tiến độ hoàn thành</span>
                    <span>{item.progress_percent}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-brand-600 transition-all"
                      style={{ width: `${item.progress_percent}%` }}
                    />
                  </div>
                </div>
                <div className="text-xs text-slate-500">
                  Phụ trách: <strong className="text-slate-800">{item.owner_detail?.display_name || "Chưa gán"}</strong>
                </div>
                {canEdit && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => openEdit(item)}
                      className="flex-1 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold hover:bg-slate-50"
                    >
                      Chỉnh sửa
                    </button>
                    <button
                      onClick={() => handleDelete(item)}
                      className="p-1.5 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">
                {editingItem ? `Chỉnh sửa ${editingItem.code}` : "Tạo Roadmap Item mới"}
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Sản phẩm</label>
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
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Người phụ trách</label>
                  <select
                    value={form.owner}
                    onChange={(e) => setForm({ ...form, owner: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                  >
                    <option value="">-- Chưa gán --</option>
                    {staff.map((u) => (
                      <option key={u.id} value={u.id}>{u.display_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <input
                type="text"
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Tên tính năng / cải tiến"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={3}
                required
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Mô tả chi tiết kế hoạch cải tiến"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={2}
                value={form.public_description}
                onChange={(e) => setForm({ ...form, public_description: e.target.value })}
                placeholder="Mô tả công khai cho khách hàng (Public Roadmap)"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={2}
                value={form.internal_notes}
                onChange={(e) => setForm({ ...form, internal_notes: e.target.value })}
                placeholder="Ghi chú kỹ thuật / chi phí nội bộ (chỉ hiện ở Private)"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />

              <div className="grid grid-cols-3 gap-2">
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="PLANNED">Planned</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="COMPLETED">Completed</option>
                </select>
                <select
                  value={form.visibility}
                  onChange={(e) => setForm({ ...form, visibility: e.target.value as RoadmapVisibility })}
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="PUBLIC">Public</option>
                  <option value="PRIVATE">Private</option>
                </select>
                <input
                  type="text"
                  value={form.quarter}
                  onChange={(e) => setForm({ ...form, quarter: e.target.value })}
                  placeholder="Q1 2027"
                  className="px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tiến độ: {form.progress_percent}%
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={form.progress_percent}
                  onChange={(e) => setForm({ ...form, progress_percent: Number(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Liên kết Insight liên quan
                </label>
                <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
                  {insights.map((ins) => (
                    <label key={ins.id} className="flex items-center gap-2 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.insight_group_ids.includes(ins.id)}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            insight_group_ids: e.target.checked
                              ? [...prev.insight_group_ids, ins.id]
                              : prev.insight_group_ids.filter((x) => x !== ins.id),
                          }))
                        }
                      />
                      <span className="truncate">
                        {ins.code} — {ins.title}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold">
                  Lưu Roadmap
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
