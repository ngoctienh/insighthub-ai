import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Lock, Mail, Sparkles } from "lucide-react";
import { getApiErrorMessage } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";

const DEMO_ACCOUNTS = [
  { label: "Admin", identifier: "admin", role: "ADMIN" },
  { label: "Product Manager", identifier: "pm_minh", role: "PRODUCT_MANAGER" },
  { label: "Developer", identifier: "dev_tuan", role: "DEVELOPER" },
  { label: "Customer Support", identifier: "cs_linh", role: "CUSTOMER_SUPPORT" },
  { label: "Customer", identifier: "customer_an", role: "CUSTOMER" },
];

export function LoginPage() {
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const user = await login(identifier, password);
      showToast(`Chào mừng ${user.display_name}!`, "success");
      navigate(user.role_code === "CUSTOMER" ? "/portal" : "/dashboard");
    } catch (err) {
      setError(getApiErrorMessage(err, "Đăng nhập thất bại."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Đăng nhập InsightHub AI</h1>
            <p className="text-xs text-slate-500">Nền tảng quản lý Feedback & Product Discovery</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Email hoặc Tên đăng nhập
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="pm@insighthub.vn hoặc pm_minh"
                className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-slate-700">Mật khẩu</label>
              <Link to="/forgot-password" className="text-xs font-medium text-brand-600 hover:underline">
                Quên mật khẩu?
              </Link>
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded-lg bg-brand-600 text-white font-semibold text-sm hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            {submitting ? "Đang xác thực..." : "Đăng nhập"}
          </button>
        </form>

        {/* Quick Demo Selector */}
        <div className="mt-6 pt-5 border-t border-slate-200">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
            Chọn nhanh tài khoản Demo (xem mật khẩu trong README)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {DEMO_ACCOUNTS.map((acc) => (
              <button
                key={acc.identifier}
                type="button"
                onClick={() => {
                  setIdentifier(acc.identifier);
                }}
                className="px-2.5 py-1 rounded-md border border-slate-200 bg-slate-50 hover:bg-brand-50 hover:border-brand-200 text-xs font-medium text-slate-700"
              >
                {acc.label}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-6 text-center text-sm text-slate-600">
          Chưa có tài khoản khách hàng?{" "}
          <Link to="/register" className="font-semibold text-brand-600 hover:underline">
            Đăng ký ngay
          </Link>
        </p>
      </div>
    </div>
  );
}
