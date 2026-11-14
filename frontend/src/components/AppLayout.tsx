import React, { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  Bell,
  Compass,
  Globe,
  Inbox,
  Kanban,
  LayoutDashboard,
  LogOut,
  Map,
  Menu,
  MessageSquarePlus,
  Radio,
  Search,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../contexts/AuthContext";

export function AppLayout({
  children,
  title,
  subtitle,
  actions,
}: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  const { user, logout, isInternal } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let mounted = true;
    const fetchUnread = async () => {
      try {
        const res = await api.get<{ unread_count: number }>("/notifications/unread_count/");
        if (mounted) setUnreadCount(res.data.unread_count);
      } catch {
        // Silent fail for badge polling
      }
    };
    fetchUnread();
    const timer = setInterval(fetchUnread, 30000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/inbox?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const navItems = isInternal
    ? [
        { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { to: "/inbox", label: "Feedback Inbox", icon: Inbox },
        { to: "/sources", label: "Multi-source Hub", icon: Radio },
        { to: "/insights", label: "AI Insights", icon: Sparkles },
        { to: "/kanban", label: "Kanban Board", icon: Kanban },
        { to: "/roadmap", label: "Product Roadmap", icon: Map },
        { to: "/public-roadmap", label: "Public Roadmap", icon: Globe },
        { to: "/notifications", label: "Thông báo", icon: Bell, badge: unreadCount },
        { to: "/users", label: "Người dùng", icon: Users },
        { to: "/settings", label: "Cài đặt", icon: Settings },
      ]
    : [
        { to: "/portal", label: "Customer Portal", icon: Compass },
        { to: "/inbox", label: "Phản hồi của tôi", icon: Inbox },
        { to: "/public-roadmap", label: "Public Roadmap", icon: Globe },
        { to: "/notifications", label: "Thông báo", icon: Bell, badge: unreadCount },
        { to: "/settings", label: "Tài khoản & Cài đặt", icon: Settings },
      ];

  const SidebarContent = (
    <div className="flex flex-col h-full bg-slate-950 text-slate-200 w-64">
      <div className="flex items-center justify-between px-5 h-16 border-b border-slate-800/80">
        <Link to={isInternal ? "/dashboard" : "/portal"} className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm shadow-brand-500/30">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-white tracking-tight">InsightHub AI</div>
            <div className="text-[11px] text-slate-400">Product Discovery</div>
          </div>
        </Link>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-600/20 text-white border border-brand-500/30"
                    : "text-slate-400 hover:text-white hover:bg-slate-900"
                }`
              }
            >
              <span className="flex items-center gap-3">
                <Icon className="w-4 h-4 shrink-0" />
                {item.label}
              </span>
              {typeof item.badge === "number" && item.badge > 0 && (
                <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-rose-500 text-white">
                  {item.badge > 99 ? "99+" : item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800/80 bg-slate-900/50">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-full bg-brand-600/30 border border-brand-500/40 flex items-center justify-center text-sm font-bold text-brand-100 shrink-0">
            {(user?.display_name || "U").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-white truncate">{user?.display_name}</div>
            <div className="text-[11px] text-indigo-300 font-medium truncate">{user?.role_name}</div>
          </div>
        </div>
        <button
          onClick={async () => {
            await logout();
            navigate("/login");
          }}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          Đăng xuất
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block shrink-0">{SidebarContent}</aside>

      {/* Mobile Drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10">{SidebarContent}</div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
            >
              <Menu className="w-5 h-5" />
            </button>
            <form onSubmit={handleGlobalSearch} className="hidden sm:flex items-center max-w-md w-full relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm feedback theo mã, tiêu đề, email..."
                className="w-full pl-9 pr-3 py-1.5 text-sm bg-slate-100 border border-transparent focus:bg-white focus:border-brand-500 rounded-lg outline-none transition-all"
              />
            </form>
          </div>

          <div className="flex items-center gap-2.5">
            <Link
              to={isInternal ? "/sources" : "/portal"}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs sm:text-sm font-medium hover:bg-brand-700 transition-colors shadow-sm"
            >
              <MessageSquarePlus className="w-4 h-4" />
              <span className="hidden sm:inline">{isInternal ? "Tiếp nhận Feedback" : "Gửi góp ý"}</span>
            </Link>
            <Link
              to="/notifications"
              className="relative p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
              title="Thông báo"
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white" />
              )}
            </Link>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto">
          {(title || actions) && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                {title && <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>}
                {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
              </div>
              {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
