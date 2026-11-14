import React, { useEffect, useState } from "react";
import { KeyRound, Plus, Save, Tag as TagIcon, User as UserIcon } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { Product, Tag } from "../types";

export function SettingsPage() {
  const { user, refreshUser, hasRole } = useAuth();
  const { showToast } = useToast();
  const canManageCatalog = hasRole("ADMIN", "PRODUCT_MANAGER");

  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
    job_title: user?.job_title || "",
    department: user?.department || "",
    email_notifications_enabled: user?.email_notifications_enabled ?? true,
  });

  const [passwords, setPasswords] = useState({
    old_password: "",
    new_password: "",
  });

  const [products, setProducts] = useState<Product[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [newProduct, setNewProduct] = useState({ name: "", slug: "", category: "SaaS / App" });
  const [newTag, setNewTag] = useState({ name: "", slug: "", color: "#4f46e5" });

  useEffect(() => {
    if (user) {
      setProfile({
        full_name: user.full_name || "",
        job_title: user.job_title || "",
        department: user.department || "",
        email_notifications_enabled: user.email_notifications_enabled ?? true,
      });
    }
  }, [user]);

  useEffect(() => {
    if (canManageCatalog) {
      api.get<Product[]>("/products/").then((r) => setProducts(r.data)).catch(() => {});
      api.get<Tag[]>("/tags/").then((r) => setTags(r.data)).catch(() => {});
    }
  }, [canManageCatalog]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.patch("/auth/me/", profile);
      await refreshUser();
      showToast("Đã cập nhật hồ sơ cá nhân.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post<{ detail: string }>("/auth/change-password/", passwords);
      showToast(res.data.detail, "success");
      setPasswords({ old_password: "", new_password: "" });
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post<Product>("/products/", newProduct);
      setProducts([...products, res.data]);
      setNewProduct({ name: "", slug: "", category: "SaaS / App" });
      showToast("Đã thêm sản phẩm mới!", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleCreateTag = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post<Tag>("/tags/", newTag);
      setTags([...tags, res.data]);
      setNewTag({ name: "", slug: "", color: "#4f46e5" });
      showToast("Đã thêm nhãn phân loại mới!", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title="Hồ sơ & Cài đặt hệ thống"
      subtitle="Quản lý thông tin tài khoản, bảo mật mật khẩu và danh mục sản phẩm/nhãn"
    >
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Profile */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h2 className="font-bold text-slate-900 flex items-center gap-2 mb-4">
            <UserIcon className="w-4 h-4 text-brand-600" />
            Hồ sơ cá nhân ({user?.role_name})
          </h2>
          <form onSubmit={handleSaveProfile} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Họ và tên</label>
              <input
                type="text"
                value={profile.full_name}
                onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Chức danh</label>
                <input
                  type="text"
                  value={profile.job_title}
                  onChange={(e) => setProfile({ ...profile, job_title: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Phòng ban</label>
                <input
                  type="text"
                  value={profile.department}
                  onChange={(e) => setProfile({ ...profile, department: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={profile.email_notifications_enabled}
                onChange={(e) =>
                  setProfile({ ...profile, email_notifications_enabled: e.target.checked })
                }
              />
              Nhận thông báo cập nhật trạng thái
            </label>
            <div className="pt-2">
              <button
                type="submit"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
              >
                <Save className="w-4 h-4" />
                Lưu thay đổi
              </button>
            </div>
          </form>
        </div>

        {/* Change Password */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h2 className="font-bold text-slate-900 flex items-center gap-2 mb-4">
            <KeyRound className="w-4 h-4 text-amber-600" />
            Đổi mật khẩu
          </h2>
          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Mật khẩu hiện tại</label>
              <input
                type="password"
                required
                value={passwords.old_password}
                onChange={(e) => setPasswords({ ...passwords, old_password: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Mật khẩu mới (tối thiểu 8 ký tự)
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={passwords.new_password}
                onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800"
            >
              Cập nhật mật khẩu
            </button>
          </form>
        </div>

        {/* Catalog Management for Admin / PM */}
        {canManageCatalog && (
          <>
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
              <h2 className="font-bold text-slate-900">Quản lý Sản phẩm ({products.length})</h2>
              <div className="space-y-2">
                {products.map((p) => (
                  <div key={p.id} className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex justify-between items-center text-sm">
                    <div>
                      <div className="font-semibold text-slate-900">{p.name}</div>
                      <div className="text-xs text-slate-500">
                        /{p.slug} · {p.category}
                      </div>
                    </div>
                    <span className="text-xs font-bold text-brand-600">{p.feedback_count ?? 0} fb</span>
                  </div>
                ))}
              </div>
              <form onSubmit={handleCreateProduct} className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100">
                <input
                  type="text"
                  required
                  placeholder="Tên sản phẩm"
                  value={newProduct.name}
                  onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs"
                />
                <input
                  type="text"
                  required
                  placeholder="slug-san-pham"
                  value={newProduct.slug}
                  onChange={(e) => setNewProduct({ ...newProduct, slug: e.target.value })}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Thêm
                </button>
              </form>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
              <h2 className="font-bold text-slate-900 flex items-center gap-2">
                <TagIcon className="w-4 h-4 text-brand-600" />
                Nhãn phân loại Feedback ({tags.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {tags.map((t) => (
                  <span
                    key={t.id}
                    className="px-3 py-1 rounded-full text-xs font-semibold border"
                    style={{
                      borderColor: `${t.color}50`,
                      backgroundColor: `${t.color}15`,
                      color: t.color,
                    }}
                  >
                    {t.name}
                  </span>
                ))}
              </div>
              <form onSubmit={handleCreateTag} className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-100">
                <input
                  type="text"
                  required
                  placeholder="Tên nhãn"
                  value={newTag.name}
                  onChange={(e) => setNewTag({ ...newTag, name: e.target.value })}
                  className="col-span-2 px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs"
                />
                <input
                  type="text"
                  required
                  placeholder="slug"
                  value={newTag.slug}
                  onChange={(e) => setNewTag({ ...newTag, slug: e.target.value })}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Thêm
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
