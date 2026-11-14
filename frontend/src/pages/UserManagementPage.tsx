import React, { useEffect, useState } from "react";
import { Plus, Shield, UserCheck, UserX, X } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { RoleCode, User } from "../types";

export function UserManagementPage() {
  const { hasRole } = useAuth();
  const { showToast } = useToast();
  const isAdmin = hasRole("ADMIN");

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    role_code: "DEVELOPER" as RoleCode,
    job_title: "",
    department: "",
    password: "",
  });

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ results: User[] }>("/users/?page_size=100");
      setUsers(res.data.results || []);
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const openCreate = () => {
    setEditing(null);
    setForm({
      username: "",
      email: "",
      full_name: "",
      role_code: "DEVELOPER",
      job_title: "",
      department: "Engineering",
      password: "",
    });
    setModalOpen(true);
  };

  const openEdit = (u: User) => {
    setEditing(u);
    setForm({
      username: u.username,
      email: u.email,
      full_name: u.full_name,
      role_code: u.role_code,
      job_title: u.job_title,
      department: u.department,
      password: "",
    });
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: Record<string, unknown> = {
        username: form.username,
        email: form.email,
        full_name: form.full_name,
        role_code: form.role_code,
        job_title: form.job_title,
        department: form.department,
      };
      if (form.password) payload.password = form.password;

      if (editing) {
        await api.patch(`/users/${editing.id}/`, payload);
        showToast("Đã cập nhật người dùng & phân quyền.", "success");
      } else {
        await api.post("/users/", payload);
        showToast("Đã tạo tài khoản thành công.", "success");
      }
      setModalOpen(false);
      loadUsers();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleToggleActive = async (u: User) => {
    try {
      await api.post(`/users/${u.id}/toggle_active/`, {});
      showToast(`Đã ${u.is_active ? "vô hiệu hóa" : "kích hoạt"} tài khoản ${u.username}`, "info");
      loadUsers();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  return (
    <AppLayout
      title="Quản lý Người dùng & Phân quyền"
      subtitle={
        isAdmin
          ? "Quản trị tài khoản và phân quyền RBAC (Admin, PM, Developer, CS, Customer)"
          : "Danh bạ thành viên phục vụ phân công xử lý (Chỉ Admin có quyền chỉnh sửa)"
      }
      actions={
        isAdmin && (
          <button
            onClick={openCreate}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
          >
            <Plus className="w-4 h-4" />
            Tạo người dùng
          </button>
        )
      }
    >
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">Đang tải danh sách...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                  <th className="py-3 px-4">Thành viên</th>
                  <th className="py-3 px-4">Vai trò (Role)</th>
                  <th className="py-3 px-4">Phòng ban & Chức danh</th>
                  <th className="py-3 px-4">Trạng thái</th>
                  {isAdmin && <th className="py-3 px-4 text-right">Thao tác</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{u.display_name}</div>
                      <div className="text-xs text-slate-500">
                        @{u.username} · {u.email}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs font-semibold">
                        <Shield className="w-3 h-3" />
                        {u.role_name}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      <div>{u.job_title || "—"}</div>
                      <div className="text-slate-400">{u.department || "—"}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                          u.is_active ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                        }`}
                      >
                        {u.is_active ? "Hoạt động" : "Tạm khóa"}
                      </span>
                    </td>
                    {isAdmin && (
                      <td className="py-3 px-4 text-right">
                        <div className="inline-flex items-center gap-2">
                          <button
                            onClick={() => openEdit(u)}
                            className="px-2.5 py-1 rounded border border-slate-300 text-xs font-medium hover:bg-slate-100"
                          >
                            Phân quyền / Sửa
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className="p-1.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                            title={u.is_active ? "Vô hiệu hóa" : "Kích hoạt"}
                          >
                            {u.is_active ? <UserX className="w-4 h-4 text-rose-600" /> : <UserCheck className="w-4 h-4 text-emerald-600" />}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">
                {editing ? `Chỉnh sửa @${editing.username}` : "Tạo người dùng mới"}
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSave} className="space-y-3">
              <input
                type="text"
                required
                disabled={Boolean(editing)}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder="Username"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm disabled:bg-slate-100"
              />
              <input
                type="text"
                required
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Họ và tên"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Email"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <select
                value={form.role_code}
                onChange={(e) => setForm({ ...form, role_code: e.target.value as RoleCode })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              >
                <option value="ADMIN">ADMIN</option>
                <option value="PRODUCT_MANAGER">PRODUCT MANAGER</option>
                <option value="DEVELOPER">DEVELOPER</option>
                <option value="CUSTOMER_SUPPORT">CUSTOMER SUPPORT</option>
                <option value="CUSTOMER">CUSTOMER</option>
              </select>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={form.job_title}
                  onChange={(e) => setForm({ ...form, job_title: e.target.value })}
                  placeholder="Chức danh"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <input
                  type="text"
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  placeholder="Phòng ban"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <input
                type="password"
                required={!editing}
                minLength={8}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={editing ? "Mật khẩu mới (để trống nếu giữ nguyên)" : "Mật khẩu (tối thiểu 8 ký tự)"}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
                  Hủy
                </button>
                <button type="submit" className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold">
                  Lưu
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
