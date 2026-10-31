import type { components } from "@/types/api.generated";
import { supabase } from "@/lib/supabase/client";
export type Schema = components["schemas"];
const base = process.env.NEXT_PUBLIC_API_BASE_URL;
export async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = false,
): Promise<T> {
  if (!base)
    throw new Error(
      "API service is not configured. Set NEXT_PUBLIC_API_BASE_URL.",
    );
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (authenticated) {
    if (!supabase) throw new Error("Sign-in service is not configured.");
    const { data, error } = await supabase.auth.getSession();
    if (error || !data.session)
      throw new Error("Sign in before submitting a private report.");
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }
  let response: Response;
  try {
    response = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new Error(
      "Could not reach CivicMesh. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | Schema["ErrorResponse"]
      | null;
    throw new Error(body?.message ?? `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}
export const api = {
  incidents: (cursor?: string) =>
    request<Schema["IncidentPage"]>(
      `/incidents${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
    ),
  incident: (id: string) =>
    request<Schema["Incident"]>(`/incidents/${encodeURIComponent(id)}`),
  prepare: (body: Schema["UploadPrepare"]) =>
    request<Schema["UploadPrepared"]>(
      "/uploads/prepare",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  report: (body: Schema["ReportCreate"], key: string) =>
    request<Schema["Submission"]>(
      "/reports",
      {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify(body),
      },
      true,
    ),
};
