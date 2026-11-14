import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  Copy,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { api, getApiErrorMessage } from "../api/client";
import { AppLayout } from "../components/AppLayout";
import { PriorityBadge, SourceBadge, StatusBadge } from "../components/Badges";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { AIAnalysisJob, Feedback, InsightGroup, Product } from "../types";

export function AIInsightsPage() {
  const { hasRole } = useAuth();
  const { showToast } = useToast();
  const canManage = hasRole("ADMIN", "PRODUCT_MANAGER");

  const [tab, setTab] = useState<"insights" | "duplicates" | "unassigned" | "jobs">("insights");
  const [insights, setInsights] = useState<InsightGroup[]>([]);
  const [unassigned, setUnassigned] = useState<Feedback[]>([]);
  const [jobs, setJobs] = useState<AIAnalysisJob[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  const [runningAI, setRunningAI] = useState(false);
  const [aiConfig, setAiConfig] = useState({
    product_id: "",
    similarity_threshold: 0.72,
    eps: 0.48,
    min_samples: 2,
    use_llm: true,
    include_clustered: false,
  });

  const [selectedFbIds, setSelectedFbIds] = useState<number[]>([]);
  const [manualTitle, setManualTitle] = useState("");
  const [manualModalOpen, setManualModalOpen] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [insRes, unRes, jobRes, prodRes] = await Promise.all([
        api.get<{ results: InsightGroup[] }>("/insights/?page_size=100"),
        api.get<Feedback[]>("/ai/unassigned/"),
        api.get<{ results: AIAnalysisJob[] }>("/ai/jobs/?page_size=20"),
        api.get<Product[]>("/products/"),
      ]);
      setInsights(insRes.data.results || []);
      setUnassigned(unRes.data || []);
      setJobs(jobRes.data.results || []);
      setProducts(prodRes.data || []);
    } catch (err) {
      showToast(getApiErrorMessage(err, "Không thể tải dữ liệu AI Insights."), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleRunAI = async () => {
    setRunningAI(true);
    try {
      const res = await api.post<AIAnalysisJob>("/ai/analyze/", {
        product_id: aiConfig.product_id ? Number(aiConfig.product_id) : null,
        similarity_threshold: aiConfig.similarity_threshold,
        eps: aiConfig.eps,
        min_samples: aiConfig.min_samples,
        use_llm: aiConfig.use_llm,
        include_clustered: aiConfig.include_clustered,
      });
      const metrics = res.data.metrics || {};
      showToast(
        `AI hoàn tất (${res.data.analysis_mode}): xử lý ${metrics.processed_count ?? 0} feedback, tạo ${
          Array.isArray(metrics.created_insight_ids) ? metrics.created_insight_ids.length : 0
        } nhóm insight.`,
        "success"
      );
      await loadAll();
    } catch (err) {
      showToast(getApiErrorMessage(err, "Lỗi khi chạy AI Pipeline."), "error");
    } finally {
      setRunningAI(false);
    }
  };

  const handleConfirmInsight = async (id: number) => {
    try {
      await api.post(`/insights/${id}/confirm/`, {});
      showToast("Đã xác nhận nhóm Insight.", "success");
      loadAll();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleRejectInsight = async (id: number) => {
    try {
      await api.post(`/insights/${id}/reject/`, {});
      showToast("Đã từ chối nhóm Insight.", "info");
      loadAll();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleConfirmDuplicatePair = async (
    targetId: number,
    dupId: number,
    score: number
  ) => {
    try {
      await api.post(`/feedbacks/${dupId}/mark_duplicate/`, {
        duplicate_of_id: targetId,
        similarity_score: score,
        confirm: true,
      });
      showToast("Đã xác nhận đánh dấu trùng lặp.", "success");
      loadAll();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const handleCreateManualInsight = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualTitle.trim() || selectedFbIds.length === 0) return;
    try {
      await api.post("/insights/", {
        product: products[0]?.id,
        title: manualTitle.trim(),
        feedback_ids: selectedFbIds,
      });
      showToast("Đã tạo nhóm Insight thủ công!", "success");
      setManualModalOpen(false);
      setManualTitle("");
      setSelectedFbIds([]);
      loadAll();
    } catch (err) {
      showToast(getApiErrorMessage(err), "error");
    }
  };

  const latestDuplicates = jobs[0]?.duplicate_candidates || [];

  return (
    <AppLayout
      title="AI Insight Engine"
      subtitle="Embedding Vector · Cosine Similarity · DBSCAN Clustering · Summarization · Priority Scoring (0.4V + 0.35I + 0.25S)"
      actions={
        <button
          onClick={loadAll}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
          Làm mới
        </button>
      }
    >
      {/* AI Control Panel for PM / Admin */}
      {canManage && (
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-5 mb-6 shadow-md">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-300 uppercase tracking-wider mb-1">
                <Sparkles className="w-3.5 h-3.5" />
                Điều khiển AI Clustering Pipeline
              </div>
              <h2 className="text-lg font-bold">
                Phân tích & Gom nhóm {unassigned.length} feedback chưa phân loại
              </h2>
              <p className="text-xs text-slate-300 mt-0.5">
                Hỗ trợ tùy chỉnh ngưỡng Cosine Similarity & tham số DBSCAN trước khi sinh Insight.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex flex-col">
                <span className="text-[10px] text-slate-300 uppercase">Ngưỡng trùng ({aiConfig.similarity_threshold})</span>
                <input
                  type="range"
                  min={0.5}
                  max={0.95}
                  step={0.02}
                  value={aiConfig.similarity_threshold}
                  onChange={(e) =>
                    setAiConfig({ ...aiConfig, similarity_threshold: Number(e.target.value) })
                  }
                  className="w-28 accent-brand-500"
                />
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] text-slate-300 uppercase">DBSCAN eps ({aiConfig.eps})</span>
                <input
                  type="range"
                  min={0.2}
                  max={0.8}
                  step={0.02}
                  value={aiConfig.eps}
                  onChange={(e) => setAiConfig({ ...aiConfig, eps: Number(e.target.value) })}
                  className="w-28 accent-brand-500"
                />
              </div>
              <label className="inline-flex items-center gap-1.5 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiConfig.include_clustered}
                  onChange={(e) =>
                    setAiConfig({ ...aiConfig, include_clustered: e.target.checked })
                  }
                />
                Gom lại nhóm chưa xác nhận
              </label>
              <button
                onClick={handleRunAI}
                disabled={runningAI}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold shadow-sm disabled:opacity-60"
              >
                <Play className="w-4 h-4" />
                {runningAI ? "AI đang phân tích..." : "Chạy AI Phân Tích"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-6">
        {[
          { key: "insights" as const, label: `Nhóm Insight (${insights.length})` },
          { key: "duplicates" as const, label: `Nghi trùng lặp (${latestDuplicates.length})` },
          { key: "unassigned" as const, label: `Chưa phân nhóm (${unassigned.length})` },
          { key: "jobs" as const, label: `Lịch sử chạy AI (${jobs.length})` },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold border transition-colors ${
              tab === t.key
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-44 rounded-2xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {tab === "insights" && (
            <div className="grid md:grid-cols-2 gap-5">
              {insights.map((ins) => (
                <div
                  key={ins.id}
                  className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between hover:border-brand-300 transition-colors"
                >
                  <div>
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-brand-600">{ins.code}</span>
                        <StatusBadge status={ins.verification_status} />
                        <StatusBadge status={ins.status} />
                      </div>
                      <PriorityBadge level={ins.priority_level} score={ins.priority_score} />
                    </div>

                    <Link
                      to={`/insights/${ins.id}`}
                      className="text-base font-bold text-slate-900 hover:text-brand-600 line-clamp-2"
                    >
                      {ins.title}
                    </Link>
                    <p className="text-sm text-slate-600 mt-1.5 line-clamp-3">{ins.description}</p>

                    <div className="mt-4 grid grid-cols-3 gap-2 text-center bg-slate-50 rounded-xl p-2.5 border border-slate-100">
                      <div>
                        <div className="text-[11px] text-slate-500">Volume (40%)</div>
                        <div className="text-sm font-bold text-slate-900">{ins.volume_score}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-slate-500">Impact (35%)</div>
                        <div className="text-sm font-bold text-slate-900">{ins.impact_score}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-slate-500">Severity (25%)</div>
                        <div className="text-sm font-bold text-slate-900">{ins.severity_score}</div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <div className="text-xs text-slate-500">
                      <strong>{ins.feedback_count}</strong> feedback ·{" "}
                      <strong>{ins.affected_customers_count}</strong> khách hàng
                    </div>
                    <div className="flex items-center gap-1.5">
                      {canManage && ins.verification_status === "PENDING_REVIEW" && (
                        <>
                          <button
                            onClick={() => handleConfirmInsight(ins.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700"
                          >
                            <Check className="w-3.5 h-3.5" />
                            Xác nhận
                          </button>
                          <button
                            onClick={() => handleRejectInsight(ins.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-rose-200 text-rose-700 text-xs font-semibold hover:bg-rose-50"
                          >
                            <X className="w-3.5 h-3.5" />
                            Từ chối
                          </button>
                        </>
                      )}
                      <Link
                        to={`/insights/${ins.id}`}
                        className="px-3 py-1 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Chi tiết
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "duplicates" && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <div className="mb-4">
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <Copy className="w-4 h-4 text-brand-600" />
                  Kiểm duyệt các cặp Feedback có Cosine Similarity cao
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  AI chỉ gợi ý ứng viên dựa trên độ tương đồng vector. Quản trị viên kiểm tra và xác nhận thủ công.
                </p>
              </div>
              {latestDuplicates.length === 0 ? (
                <p className="text-sm text-slate-500 py-8 text-center">
                  Chưa có cặp nghi trùng lặp nào từ lần chạy AI gần nhất.
                </p>
              ) : (
                <div className="space-y-3">
                  {latestDuplicates.map((pair, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3"
                    >
                      <div className="space-y-1 text-sm">
                        <div>
                          <Link to={`/inbox/${pair.feedback_a_id}`} className="font-semibold text-brand-600 hover:underline">
                            {pair.feedback_a_code}: {pair.feedback_a_title}
                          </Link>
                        </div>
                        <div>
                          <Link to={`/inbox/${pair.feedback_b_id}`} className="font-semibold text-slate-900 hover:underline">
                            {pair.feedback_b_code}: {pair.feedback_b_title}
                          </Link>
                        </div>
                        <div className="text-xs text-slate-500">
                          Cosine Similarity: <strong>{(pair.similarity_score * 100).toFixed(1)}%</strong>
                          {pair.is_exact_normalized_match && " · Trùng văn bản chuẩn hóa"}
                        </div>
                      </div>
                      {canManage && (
                        <button
                          onClick={() =>
                            handleConfirmDuplicatePair(
                              pair.feedback_a_id,
                              pair.feedback_b_id,
                              pair.similarity_score
                            )
                          }
                          className="px-3.5 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 shrink-0"
                        >
                          Xác nhận {pair.feedback_b_code} trùng {pair.feedback_a_code}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "unassigned" && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div>
                  <h3 className="font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-brand-600" />
                    Feedback chưa thuộc nhóm Insight nào ({unassigned.length})
                  </h3>
                  <p className="text-xs text-slate-500">
                    Các phản hồi mới hoặc nhiễu (DBSCAN label = -1) có thể chạy AI hoặc gom nhóm thủ công.
                  </p>
                </div>
                {canManage && selectedFbIds.length > 0 && (
                  <button
                    onClick={() => setManualModalOpen(true)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-brand-600 text-white text-xs font-semibold"
                  >
                    <Plus className="w-4 h-4" />
                    Tạo nhóm thủ công ({selectedFbIds.length})
                  </button>
                )}
              </div>

              {unassigned.length === 0 ? (
                <p className="text-sm text-slate-500 py-8 text-center">Tất cả feedback đã được gom nhóm!</p>
              ) : (
                <div className="space-y-2.5">
                  {unassigned.map((fb) => (
                    <label
                      key={fb.id}
                      className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer"
                    >
                      {canManage && (
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedFbIds.includes(fb.id)}
                          onChange={(e) => {
                            setSelectedFbIds((prev) =>
                              e.target.checked
                                ? [...prev, fb.id]
                                : prev.filter((x) => x !== fb.id)
                            );
                          }}
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <span className="text-xs font-mono font-bold text-brand-600">{fb.code}</span>
                          <SourceBadge code={fb.source_code} />
                          <PriorityBadge level={fb.impact_level} />
                        </div>
                        <Link to={`/inbox/${fb.id}`} className="font-semibold text-sm text-slate-900 hover:underline">
                          {fb.title}
                        </Link>
                        <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">{fb.content}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "jobs" && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-3">
              {jobs.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-6">Chưa có lịch sử chạy AI Pipeline.</p>
              ) : (
                jobs.map((job) => (
                  <div key={job.id} className="p-4 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">Job #{job.id}</span>
                        <StatusBadge status={job.status} />
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono">
                          {job.analysis_mode}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        Xử lý: {String(job.metrics?.processed_count ?? 0)} feedback · Nhóm mới:{" "}
                        {String(job.metrics?.clusters_count ?? 0)} · Thời gian:{" "}
                        {String(job.metrics?.duration_ms ?? 0)}ms
                      </div>
                    </div>
                    <div className="text-xs text-slate-400">
                      {new Date(job.created_at).toLocaleString("vi-VN")}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}

      {/* Manual Insight Modal */}
      {manualModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900 mb-3">Tạo nhóm Insight thủ công</h3>
            <form onSubmit={handleCreateManualInsight} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tên nhóm Insight</label>
                <input
                  type="text"
                  required
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Ví dụ: Lỗi xác thực mã OTP chậm"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <p className="text-xs text-slate-500">
                Đã chọn {selectedFbIds.length} feedback. Hệ thống sẽ tự tính điểm ưu tiên và tóm tắt cho nhóm mới.
              </p>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setManualModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold"
                >
                  Tạo Insight
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
