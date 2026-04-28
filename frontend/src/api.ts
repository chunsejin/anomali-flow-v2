import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface ApiEnvelope<T> {
  tenant_id: string | null;
  submitted_by: string | null;
  trace_id: string;
  request_id: string;
  policy_version: string;
  data: T | null;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  } | null;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export function authHeader(token?: string): Record<string, string> {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function getEnvelope<T>(
  path: string,
  token?: string,
  params?: Record<string, unknown>,
): Promise<ApiEnvelope<T>> {
  const res = await api.get<ApiEnvelope<T>>(path, {
    params,
    headers: {
      ...authHeader(token),
      "X-Request-Id": crypto.randomUUID(),
    },
  });
  return res.data;
}

export interface ShapExplanation {
  task_id: string;
  algorithm: string;
  method: string;
  feature_importance: Record<string, number>;
  outlier_explanations: Record<
    string,
    Array<{
      feature: string;
      shap_value: number;
      abs_shap_value: number;
    }>
  >;
  n_samples_analyzed: number;
  n_outliers_analyzed: number;
}

export async function getTaskExplanations(
  taskId: string,
  token?: string,
): Promise<ApiEnvelope<ShapExplanation>> {
  return getEnvelope<ShapExplanation>(`/tasks/${taskId}/explanations`, token);
}

export async function requestTaskExplanation(
  taskId: string,
  token?: string,
): Promise<ApiEnvelope<Record<string, unknown>>> {
  const res = await api.post<ApiEnvelope<Record<string, unknown>>>(
    `/tasks/${taskId}/request-explanation`,
    {},
    {
      headers: {
        ...authHeader(token),
        "X-Request-Id": crypto.randomUUID(),
      },
    },
  );
  return res.data;
}

