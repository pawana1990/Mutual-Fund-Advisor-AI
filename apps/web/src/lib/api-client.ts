/**
 * Thin fetch wrapper for the FastAPI backend (see docs/API_DESIGN.md).
 * Attaches the Cognito access token (read from wherever the auth layer
 * stashes it — see `getAccessToken` below) and normalizes RFC 7807 error
 * bodies into a typed `ApiError`.
 */
import type {
  Alert,
  ChatResponse,
  Goal,
  HealthScore,
  Holding,
  Portfolio,
  Recommendation,
  Snapshot,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, title: string, detail?: string) {
    super(title);
    this.status = status;
    this.detail = detail;
  }
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.title ?? response.statusText, body.detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  portfolios: {
    list: () => request<Portfolio[]>("/portfolios"),
    get: (id: string) => request<Portfolio>(`/portfolios/${id}`),
    holdings: (id: string) => request<Holding[]>(`/portfolios/${id}/holdings`),
    snapshot: (id: string) => request<Snapshot>(`/portfolios/${id}/snapshot`),
    healthScore: (id: string) => request<HealthScore>(`/portfolios/${id}/health-score`),
    recommendations: (id: string, status?: string) =>
      request<Recommendation[]>(`/portfolios/${id}/recommendations${status ? `?status_filter=${status}` : ""}`),
    recompute: (id: string) => request<HealthScore>(`/portfolios/${id}/recompute`, { method: "POST" }),
    goals: (id: string) => request<Goal[]>(`/portfolios/${id}/goals`),
    chat: (id: string, message: string) =>
      request<ChatResponse>(`/portfolios/${id}/chat`, { method: "POST", body: JSON.stringify({ message }) }),
  },
  recommendations: {
    accept: (id: string) => request<Recommendation>(`/recommendations/${id}/accept`, { method: "POST", body: "{}" }),
    dismiss: (id: string) => request<Recommendation>(`/recommendations/${id}/dismiss`, { method: "POST", body: "{}" }),
  },
  alerts: {
    list: (unreadOnly = false) => request<Alert[]>(`/alerts${unreadOnly ? "?unread_only=true" : ""}`),
    markRead: (id: string) => request<Alert>(`/alerts/${id}/read`, { method: "PATCH" }),
  },
};
