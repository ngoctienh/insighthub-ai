import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import { AIInsightsPage } from "./pages/AIInsightsPage";
import { CustomerPortalPage } from "./pages/CustomerPortalPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FeedbackDetailPage } from "./pages/FeedbackDetailPage";
import { FeedbackInboxPage } from "./pages/FeedbackInboxPage";
import { ForgotResetPasswordPage } from "./pages/ForgotResetPasswordPage";
import { InsightDetailPage } from "./pages/InsightDetailPage";
import { KanbanBoardPage } from "./pages/KanbanBoardPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { MultiSourceHubPage } from "./pages/MultiSourceHubPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ProductRoadmapPage } from "./pages/ProductRoadmapPage";
import { PublicRoadmapPage } from "./pages/PublicRoadmapPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UserManagementPage } from "./pages/UserManagementPage";

const INTERNAL_ROLES = [
  "ADMIN",
  "PRODUCT_MANAGER",
  "DEVELOPER",
  "CUSTOMER_SUPPORT",
] as const;

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotResetPasswordPage />} />
            <Route path="/public-roadmap" element={<PublicRoadmapPage />} />

            {/* Internal Team routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/sources"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <MultiSourceHubPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/insights"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <AIInsightsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/insights/:id"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <InsightDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/kanban"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <KanbanBoardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/roadmap"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <ProductRoadmapPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/users"
              element={
                <ProtectedRoute allowedRoles={[...INTERNAL_ROLES]}>
                  <UserManagementPage />
                </ProtectedRoute>
              }
            />

            {/* Shared Authenticated routes */}
            <Route
              path="/inbox"
              element={
                <ProtectedRoute>
                  <FeedbackInboxPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/inbox/:id"
              element={
                <ProtectedRoute>
                  <FeedbackDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/notifications"
              element={
                <ProtectedRoute>
                  <NotificationsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portal"
              element={
                <ProtectedRoute>
                  <CustomerPortalPage />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
