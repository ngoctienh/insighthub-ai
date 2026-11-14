import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { useToast } from "../contexts/ToastContext";

export function ForgotResetPasswordPage() {
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [step, setStep] = useState<"forgot" | "reset">("forgot");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [devPreviewToken, setDevPreviewToken] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ detail: string; dev_reset_token?: string }>(
        "/auth/forgot-password/",
        { email }
      );
      showToast(res.data.detail, "success");
      if (res.data.dev_reset_token) {
        setDevPreviewToken(res.data.dev_reset_token);
        setToken(res.data.dev_reset_token);
      }
      setStep("reset");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ detail: string }>("/auth/reset-password/", {
        token,
        new_password: newPassword,
      });
      showToast(res.data.detail, "success");
      navigate("/login");
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Khôi phục mật khẩu</h1>
            <p className="text-xs text-slate-500">Xác thực bằng mã token bảo mật có thời hạn 30 phút</p>
          </div>
        </div>

        {step === "forgot" ? (
          <form onSubmit={handleRequestReset} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email đã đăng ký</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand-600 text-white font-semibold text-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? "Đang gửi yêu cầu..." : "Gửi mã khôi phục"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleConfirmReset} className="space-y-4">
            {devPreviewToken && (
              <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-800">
                <strong>Chế độ Dev Local:</strong> Token khôi phục đã được điền sẵn ({devPreviewToken.slice(0, 12)}...).
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Mã Reset Token</label>
              <input
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Mật khẩu mới</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand-600 text-white font-semibold text-sm hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? "Đang cập nhật..." : "Đặt lại mật khẩu"}
            </button>
          </form>
        )}

        <div className="mt-6 text-center text-sm">
          <Link to="/login" className="text-brand-600 font-medium hover:underline">
            Quay lại đăng nhập
          </Link>
        </div>
      </div>
    </div>
  );
}
