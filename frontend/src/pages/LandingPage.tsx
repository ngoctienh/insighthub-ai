import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Globe,
  Kanban,
  Layers,
  Mail,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export function LandingPage() {
  const { user, isInternal } = useAuth();

  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center shadow-sm">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">InsightHub AI</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/public-roadmap"
              className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2"
            >
              Public Roadmap
            </Link>
            {user ? (
              <Link
                to={isInternal ? "/dashboard" : "/portal"}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
              >
                Vào ứng dụng
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-sm font-medium text-slate-700 hover:text-slate-900 px-3 py-2"
                >
                  Đăng nhập
                </Link>
                <Link
                  to="/register"
                  className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800"
                >
                  Đăng ký miễn phí
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-indigo-50/70 via-white to-white pt-16 pb-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-semibold mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            AI-powered Product Discovery & Feedback Management SaaS
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-[1.12]">
            Biến hàng ngàn feedback rời rạc thành{" "}
            <span className="text-brand-600">Product Roadmap</span> có căn cứ
          </h1>
          <p className="mt-6 text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
            InsightHub AI tự động hợp nhất phản hồi từ Web Form, Email, Live Chat & Cộng đồng,
            dùng Vector Embedding + Cosine Similarity + DBSCAN để gom nhóm Insight, chấm điểm ưu tiên{" "}
            <code className="px-1.5 py-0.5 rounded bg-slate-100 text-sm font-mono">0.4V + 0.35I + 0.25S</code>{" "}
            và kết nối trực tiếp tới Kanban & Roadmap.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              to={user ? (isInternal ? "/dashboard" : "/portal") : "/login"}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-600 text-white font-semibold hover:bg-brand-700 shadow-lg shadow-brand-600/20"
            >
              Trải nghiệm ngay
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/public-roadmap"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-slate-300 bg-white text-slate-700 font-semibold hover:bg-slate-50"
            >
              <Globe className="w-4 h-4 text-brand-600" />
              Xem Public Roadmap
            </Link>
          </div>

          {/* 4-Channel Strip */}
          <div className="mt-14 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            {[
              { icon: Globe, title: "Website Form", desc: "Cổng phản hồi khách hàng" },
              { icon: Mail, title: "Email Support", desc: "Đồng bộ hòm thư CSKH" },
              { icon: MessageSquare, title: "Live Chat", desc: "Trích xuất từ hội thoại" },
              { icon: Users, title: "Community", desc: "Ý kiến & vote cộng đồng" },
            ].map((ch) => {
              const Icon = ch.icon;
              return (
                <div
                  key={ch.title}
                  className="p-4 rounded-xl border border-slate-200 bg-white shadow-sm text-left"
                >
                  <Icon className="w-5 h-5 text-brand-600 mb-2" />
                  <div className="font-semibold text-sm text-slate-900">{ch.title}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{ch.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Core Workflow */}
      <section className="py-16 border-t border-slate-100 bg-slate-50/70">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-3xl font-bold text-slate-900">Quy trình Product Discovery khép kín</h2>
            <p className="text-slate-600 mt-2">
              Không chỉ là chatbot — nền tảng dữ liệu thực tế cho Product Manager, CS, Dev và Khách hàng.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: Layers,
                title: "1. AI Similarity & Clustering",
                desc: "Tiền xử lý tiếng Việt, tạo Embedding, tính Cosine Similarity phát hiện trùng lặp để PM kiểm duyệt và chạy DBSCAN gom cụm Insight.",
              },
              {
                icon: BarChart3,
                title: "2. Tóm tắt & Chấm điểm Ưu tiên",
                desc: "Tóm tắt vấn đề có kiểm chứng, đề xuất hướng xử lý, tạo nháp phản hồi khách hàng và tính điểm Priority = 0.4V + 0.35I + 0.25S.",
              },
              {
                icon: Kanban,
                title: "3. Kanban, Roadmap & Thông báo",
                desc: "Kéo thả Insight qua 5 trạng thái Kanban, phát hành Public/Private Roadmap và gửi thông báo tự động tới người dùng.",
              },
            ].map((feat) => {
              const Icon = feat.icon;
              return (
                <div key={feat.title} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                  <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center mb-4">
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="font-bold text-lg text-slate-900">{feat.title}</h3>
                  <p className="text-sm text-slate-600 mt-2 leading-relaxed">{feat.desc}</p>
                </div>
              );
            })}
          </div>

          <div className="mt-10 bg-white rounded-2xl border border-slate-200 p-6 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-slate-900">
                  Phân quyền RBAC chặt chẽ ở tầng Backend & PostgreSQL
                </div>
                <div className="text-sm text-slate-600">
                  Hỗ trợ đầy đủ 5 vai trò: Admin, Product Manager, Developer, Customer Support và Customer.
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              JWT Auth · Django DRF · FastAPI AI · PostgreSQL
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
