import { Globe, Mail, MessageSquare, Users } from "lucide-react";

const PRIORITY_STYLES: Record<string, string> = {
  CRITICAL: "bg-rose-50 text-rose-700 border-rose-200",
  HIGH: "bg-orange-50 text-orange-700 border-orange-200",
  MEDIUM: "bg-amber-50 text-amber-700 border-amber-200",
  LOW: "bg-slate-100 text-slate-700 border-slate-200",
};

const STATUS_STYLES: Record<string, string> = {
  NEW: "bg-sky-50 text-sky-700 border-sky-200",
  TRIAGING: "bg-indigo-50 text-indigo-700 border-indigo-200",
  ANALYZING: "bg-violet-50 text-violet-700 border-violet-200",
  PLANNED: "bg-amber-50 text-amber-700 border-amber-200",
  IN_PROGRESS: "bg-blue-50 text-blue-700 border-blue-200",
  COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  CLOSED: "bg-slate-100 text-slate-600 border-slate-200",
  DUPLICATE: "bg-zinc-100 text-zinc-600 border-zinc-300",
  PENDING_REVIEW: "bg-amber-50 text-amber-700 border-amber-200",
  CONFIRMED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  REJECTED: "bg-rose-50 text-rose-700 border-rose-200",
};

const STATUS_LABELS: Record<string, string> = {
  NEW: "Mới",
  TRIAGING: "Đang phân loại",
  ANALYZING: "Đang phân tích",
  PLANNED: "Đã lên kế hoạch",
  IN_PROGRESS: "Đang xử lý",
  COMPLETED: "Hoàn thành",
  CLOSED: "Đã đóng",
  DUPLICATE: "Trùng lặp",
  PENDING_REVIEW: "Chờ xác nhận",
  CONFIRMED: "Đã xác nhận",
  REJECTED: "Đã từ chối",
};

export function PriorityBadge({ level, score }: { level: string; score?: number | null }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
        PRIORITY_STYLES[level] || PRIORITY_STYLES.LOW
      }`}
    >
      {level}
      {typeof score === "number" && <span className="opacity-80">· {score}</span>}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        STATUS_STYLES[status] || STATUS_STYLES.NEW
      }`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export function SourceBadge({ code }: { code: string }) {
  const map: Record<string, { label: string; icon: JSX.Element; cls: string }> = {
    WEB_FORM: {
      label: "Website Form",
      icon: <Globe className="w-3.5 h-3.5" />,
      cls: "bg-indigo-50 text-indigo-700 border-indigo-200",
    },
    EMAIL: {
      label: "Email",
      icon: <Mail className="w-3.5 h-3.5" />,
      cls: "bg-cyan-50 text-cyan-700 border-cyan-200",
    },
    LIVE_CHAT: {
      label: "Live Chat",
      icon: <MessageSquare className="w-3.5 h-3.5" />,
      cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    COMMUNITY: {
      label: "Cộng đồng",
      icon: <Users className="w-3.5 h-3.5" />,
      cls: "bg-purple-50 text-purple-700 border-purple-200",
    },
  };
  const cfg = map[code] || map.WEB_FORM;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${cfg.cls}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  );
}
