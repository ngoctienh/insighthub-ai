import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("insighthub_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let pendingQueue: Array<(token: string | null) => void> = [];

function resolveQueue(token: string | null) {
  pendingQueue.forEach((cb) => cb(token));
  pendingQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login/") &&
      !originalRequest.url?.includes("/auth/token/refresh/")
    ) {
      const refresh = localStorage.getItem("insighthub_refresh_token");
      if (!refresh) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push((newToken) => {
            if (!newToken) return reject(error);
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const res = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh,
        });
        const newAccess = res.data.access;
        localStorage.setItem("insighthub_access_token", newAccess);
        if (res.data.refresh) {
          localStorage.setItem("insighthub_refresh_token", res.data.refresh);
        }
        resolveQueue(newAccess);
        originalRequest.headers.Authorization = `Bearer ${newAccess}`;
        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem("insighthub_access_token");
        localStorage.removeItem("insighthub_refresh_token");
        resolveQueue(null);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export function getApiErrorMessage(err: unknown, fallback = "Đã có lỗi xảy ra."): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as
      | { detail?: string; errors?: Record<string, string[] | string> }
      | undefined;
    if (data?.errors && typeof data.errors === "object") {
      const firstKey = Object.keys(data.errors)[0];
      if (firstKey) {
        const val = data.errors[firstKey];
        const msg = Array.isArray(val) ? val[0] : val;
        if (msg) return `${firstKey}: ${msg}`;
      }
    }
    if (data?.detail) return data.detail;
  }
  return fallback;
}
