import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Globe, Mail, MessageSquare, Send, Users, Webhook } from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { useToast } from "../contexts/ToastContext";
import { FeedbackSource, Product } from "../types";

type SourceTab = "WEB_FORM" | "EMAIL" | "LIVE_CHAT" | "COMMUNITY";

const SAMPLE_EMAILS = [
  {
    sender_name: "Lê Minh Hoàng",
    sender_email: "hoang.le@gmail.com",
    subject: "[Khẩn] Thanh toán MoMo bị trừ tiền nhưng đơn chưa lên",
    content: "Tôi thanh toán đơn 210.000đ bằng ví MoMo lúc 12h05, ví báo đã trừ tiền nhưng app Bếp Việt Go quay vòng rồi báo giao dịch thất bại.",
    impact_level: "CRITICAL",
  },
  {
    sender_name: "Nguyễn Thu Trang",
    sender_email: "trang.nguyen@yahoo.com",
    subject: "Không nhận được thông báo khi tài xế tới cổng",
    content: "Shipper đứng chờ 10 phút ngoài cổng gọi mới biết vì ứng dụng hoàn toàn không gửi thông báo đẩy.",
    impact_level: "HIGH",
  },
];

export function MultiSourceHubPage() {
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [tab, setTab] = useState<SourceTab>("WEB_FORM");
  const [products, setProducts] = useState<Product[]>([]);
  const [sources, setSources] = useState<FeedbackSource[]>([]);
  const [productId, setProductId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  const [webForm, setWebForm] = useState({
    sender_name: "",
    sender_email: "",
    title: "",
    content: "",
    impact_level: "MEDIUM",
  });

  const [emailSim, setEmailSim] = useState({
    sender_name: SAMPLE_EMAILS[0].sender_name,
    sender_email: SAMPLE_EMAILS[0].sender_email,
    subject: SAMPLE_EMAILS[0].subject,
    content: SAMPLE_EMAILS[0].content,
    impact_level: SAMPLE_EMAILS[0].impact_level,
  });

  const [chatMessages, setChatMessages] = useState([
    { role: "customer", text: "Chào shop, mình vừa đặt đơn nhưng không áp dụng được mã giảm giá 30k." },
    { role: "agent", text: "Chào bạn, bạn vui lòng cho mình biết giá trị đơn và thông báo lỗi trên màn hình nhé." },
    { role: "customer", text: "Đơn 180k vượt mức tối thiểu 120k rồi nhưng cứ bấm chọn voucher là báo lỗi không hợp lệ." },
  ]);
  const [chatDraft, setChatDraft] = useState("");
  const [chatMeta, setChatMeta] = useState({
    sender_name: "Trần Bảo Ngọc",
    sender_email: "ngoc.tran@gmail.com",
    title: "Không áp dụng được mã giảm giá dù đơn vượt mức tối thiểu",
    impact_level: "HIGH",
  });

  const [communitySim, setCommunitySim] = useState({
    sender_name: "Cộng đồng FoodLover",
    sender_email: "member.community@gmail.com",
    topic: "Góp ý cải tiến ứng dụng",
    upvotes: 24,
    title: "Đề xuất cho phép hẹn giờ giao cố định buổi trưa văn phòng",
    content: "Nhóm văn phòng tụi mình hay đặt cơm trưa lúc 10h để 11h45 giao đúng giờ nghỉ trưa.",
    impact_level: "MEDIUM",
  });

  useEffect(() => {
    api.get<Product[]>("/products/").then((r) => {
      setProducts(r.data);
      if (r.data[0]) setProductId(String(r.data[0].id));
    }).catch(() => {});
    api.get<FeedbackSource[]>("/sources/").then((r) => setSources(r.data)).catch(() => {});
  }, []);

  const ingest = async (payload: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      const res = await api.post<{ id: number; code: string }>("/sources/ingest/", {
        ...payload,
        product_id: productId ? Number(productId) : undefined,
      });
      showToast(`Đã tiếp nhận ${res.data.code} vào PostgreSQL!`, "success");
      navigate(`/inbox/${res.data.id}`);
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const currentSource = sources.find((s) => s.code === tab);

  return (
    <AppLayout
      title="Multi-source Feedback Hub"
      subtitle="Giả lập & tiếp nhận phản hồi thực tế từ 4 kênh vào cùng một bảng feedbacks trong PostgreSQL"
    >
      {/* Channel Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { code: "WEB_FORM" as SourceTab, label: "Website Form", icon: Globe },
          { code: "EMAIL" as SourceTab, label: "Email Inbox Sim", icon: Mail },
          { code: "LIVE_CHAT" as SourceTab, label: "Live Chat Sim", icon: MessageSquare },
          { code: "COMMUNITY" as SourceTab, label: "Community Sim", icon: Users },
        ].map((item) => {
          const Icon = item.icon;
          const active = tab === item.code;
          const count = sources.find((s) => s.code === item.code)?.feedback_count;
          return (
            <button
              key={item.code}
              onClick={() => setTab(item.code)}
              className={`p-4 rounded-2xl border text-left transition-all ${
                active
                  ? "bg-brand-600 text-white border-brand-600 shadow-md shadow-brand-600/20"
                  : "bg-white text-slate-800 border-slate-200 hover:border-brand-300"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <Icon className="w-5 h-5" />
                {typeof count === "number" && (
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </div>
              <div className="font-semibold text-sm">{item.label}</div>
            </button>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-bold text-slate-900">
              {tab === "WEB_FORM" && "Biểu mẫu phản hồi Website"}
              {tab === "EMAIL" && "Mô phỏng Hộp thư Email CSKH"}
              {tab === "LIVE_CHAT" && "Mô phỏng Hội thoại Live Chat"}
              {tab === "COMMUNITY" && "Mô phỏng Bài đăng Cộng đồng Người dùng"}
            </h2>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {tab === "WEB_FORM" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ingest({
                  source_code: "WEB_FORM",
                  ...webForm,
                  source_metadata: { origin: "website_widget", browser: navigator.userAgent.slice(0, 50) },
                });
              }}
              className="space-y-4"
            >
              <div className="grid sm:grid-cols-2 gap-3">
                <input
                  type="text"
                  required
                  placeholder="Tên khách hàng"
                  value={webForm.sender_name}
                  onChange={(e) => setWebForm({ ...webForm, sender_name: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <input
                  type="email"
                  required
                  placeholder="Email khách hàng"
                  value={webForm.sender_email}
                  onChange={(e) => setWebForm({ ...webForm, sender_email: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div className="grid sm:grid-cols-3 gap-3">
                <input
                  type="text"
                  required
                  placeholder="Tiêu đề phản hồi"
                  value={webForm.title}
                  onChange={(e) => setWebForm({ ...webForm, title: e.target.value })}
                  className="sm:col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <select
                  value={webForm.impact_level}
                  onChange={(e) => setWebForm({ ...webForm, impact_level: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
              <textarea
                required
                rows={4}
                placeholder="Nội dung chi tiết từ Website Form..."
                value={webForm.content}
                onChange={(e) => setWebForm({ ...webForm, content: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700"
              >
                <Send className="w-4 h-4" />
                Gửi qua Website Form
              </button>
            </form>
          )}

          {tab === "EMAIL" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {SAMPLE_EMAILS.map((sample, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setEmailSim(sample)}
                    className="px-3 py-1 rounded-full bg-cyan-50 border border-cyan-200 text-cyan-800 text-xs font-medium hover:bg-cyan-100"
                  >
                    Nạp mẫu Email #{idx + 1}: {sample.subject.slice(0, 36)}...
                  </button>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  ingest({
                    source_code: "EMAIL",
                    title: emailSim.subject,
                    content: emailSim.content,
                    sender_name: emailSim.sender_name,
                    sender_email: emailSim.sender_email,
                    impact_level: emailSim.impact_level,
                    external_reference_id: `email-${Date.now()}`,
                    source_metadata: { subject: emailSim.subject, inbox: "hotro@bepvietgo.vn" },
                  });
                }}
                className="space-y-3"
              >
                <div className="grid sm:grid-cols-2 gap-3">
                  <input
                    type="text"
                    required
                    value={emailSim.sender_name}
                    onChange={(e) => setEmailSim({ ...emailSim, sender_name: e.target.value })}
                    placeholder="From Name"
                    className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                  <input
                    type="email"
                    required
                    value={emailSim.sender_email}
                    onChange={(e) => setEmailSim({ ...emailSim, sender_email: e.target.value })}
                    placeholder="From Email"
                    className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div className="grid sm:grid-cols-3 gap-3">
                  <input
                    type="text"
                    required
                    value={emailSim.subject}
                    onChange={(e) => setEmailSim({ ...emailSim, subject: e.target.value })}
                    placeholder="Email Subject"
                    className="sm:col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                  <select
                    value={emailSim.impact_level}
                    onChange={(e) => setEmailSim({ ...emailSim, impact_level: e.target.value })}
                    className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </div>
                <textarea
                  rows={5}
                  required
                  value={emailSim.content}
                  onChange={(e) => setEmailSim({ ...emailSim, content: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono"
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-600 text-white text-sm font-semibold hover:bg-cyan-700"
                >
                  <Mail className="w-4 h-4" />
                  Giả lập nhận Email vào Inbox
                </button>
              </form>
            </div>
          )}

          {tab === "LIVE_CHAT" && (
            <div className="space-y-4">
              <div className="border border-slate-200 rounded-xl bg-slate-50 p-4 space-y-2.5 max-h-60 overflow-y-auto">
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === "customer" ? "justify-start" : "justify-end"}`}
                  >
                    <div
                      className={`max-w-[80%] px-3.5 py-2 rounded-2xl text-xs leading-relaxed ${
                        msg.role === "customer"
                          ? "bg-white border border-slate-200 text-slate-800"
                          : "bg-emerald-600 text-white"
                      }`}
                    >
                      <span className="font-bold block mb-0.5">
                        {msg.role === "customer" ? "Khách hàng" : "CSKH"}
                      </span>
                      {msg.text}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatDraft}
                  onChange={(e) => setChatDraft(e.target.value)}
                  placeholder="Thêm tin nhắn giả lập của khách hàng vào đoạn chat..."
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (chatDraft.trim()) {
                      setChatMessages([...chatMessages, { role: "customer", text: chatDraft.trim() }]);
                      setChatDraft("");
                    }
                  }}
                  className="px-3.5 py-2 rounded-lg border border-slate-300 text-xs font-semibold hover:bg-slate-50"
                >
                  + Thêm tin nhắn
                </button>
              </div>
              <div className="grid sm:grid-cols-3 gap-3">
                <input
                  type="text"
                  value={chatMeta.sender_name}
                  onChange={(e) => setChatMeta({ ...chatMeta, sender_name: e.target.value })}
                  placeholder="Tên khách"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <input
                  type="email"
                  value={chatMeta.sender_email}
                  onChange={(e) => setChatMeta({ ...chatMeta, sender_email: e.target.value })}
                  placeholder="Email khách"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <select
                  value={chatMeta.impact_level}
                  onChange={(e) => setChatMeta({ ...chatMeta, impact_level: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
              <input
                type="text"
                value={chatMeta.title}
                onChange={(e) => setChatMeta({ ...chatMeta, title: e.target.value })}
                placeholder="Tóm tắt vấn đề từ phiên Live Chat"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <button
                type="button"
                disabled={submitting}
                onClick={() =>
                  ingest({
                    source_code: "LIVE_CHAT",
                    title: chatMeta.title,
                    content: chatMessages
                      .filter((m) => m.role === "customer")
                      .map((m) => m.text)
                      .join(" "),
                    sender_name: chatMeta.sender_name,
                    sender_email: chatMeta.sender_email,
                    impact_level: chatMeta.impact_level,
                    external_reference_id: `chat-${Date.now()}`,
                    source_metadata: { transcript: chatMessages },
                  })
                }
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
              >
                <MessageSquare className="w-4 h-4" />
                Chuyển đoạn Chat thành Feedback
              </button>
            </div>
          )}

          {tab === "COMMUNITY" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ingest({
                  source_code: "COMMUNITY",
                  title: communitySim.title,
                  content: communitySim.content,
                  sender_name: communitySim.sender_name,
                  sender_email: communitySim.sender_email,
                  impact_level: communitySim.impact_level,
                  external_reference_id: `post-${Date.now()}`,
                  source_metadata: { topic: communitySim.topic, community_upvotes: communitySim.upvotes },
                });
              }}
              className="space-y-3"
            >
              <div className="grid sm:grid-cols-3 gap-3">
                <input
                  type="text"
                  required
                  value={communitySim.sender_name}
                  onChange={(e) => setCommunitySim({ ...communitySim, sender_name: e.target.value })}
                  placeholder="Tác giả bài đăng"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <input
                  type="email"
                  required
                  value={communitySim.sender_email}
                  onChange={(e) => setCommunitySim({ ...communitySim, sender_email: e.target.value })}
                  placeholder="Email"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
                <input
                  type="number"
                  min={0}
                  value={communitySim.upvotes}
                  onChange={(e) => setCommunitySim({ ...communitySim, upvotes: Number(e.target.value) })}
                  placeholder="Upvotes"
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <input
                type="text"
                required
                value={communitySim.title}
                onChange={(e) => setCommunitySim({ ...communitySim, title: e.target.value })}
                placeholder="Tiêu đề bài thảo luận"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <textarea
                rows={4}
                required
                value={communitySim.content}
                onChange={(e) => setCommunitySim({ ...communitySim, content: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-purple-600 text-white text-sm font-semibold hover:bg-purple-700"
              >
                <Users className="w-4 h-4" />
                Thu thập từ Cộng đồng
              </button>
            </form>
          )}
        </div>

        {/* External Integration Documentation Card */}
        <div className="bg-slate-900 text-slate-100 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-indigo-300 font-bold text-sm">
            <Webhook className="w-4 h-4" />
            Webhook API tích hợp nguồn ngoài
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Hệ thống cho phép các dịch vụ bên ngoài (Zendesk, Gmail Forwarder, Intercom, Discord Bot)
            gửi trực tiếp feedback vào bảng <code className="text-indigo-200">feedbacks</code> qua HTTP POST:
          </p>
          <div className="text-xs font-mono bg-slate-950 rounded-xl p-3 border border-slate-800 overflow-x-auto">
            <div className="text-emerald-400">POST /api/sources/ingest/</div>
            <div className="text-slate-400 mt-1">
              X-Source-Token: {currentSource?.webhook_token || "wh_..."}
            </div>
            <pre className="mt-2 text-slate-200">{JSON.stringify(
              {
                source_code: tab,
                title: "Ví dụ sự cố từ Webhook",
                content: "Mô tả chi tiết phản hồi...",
                sender_name: "Khách hàng",
                sender_email: "khach@example.com",
                impact_level: "HIGH",
              },
              null,
              2
            )}</pre>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
