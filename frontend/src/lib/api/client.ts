import { getAuthHeaders } from '../supabase/client';
import type { components } from '../../types/api.generated';

export type ApiReport = components['schemas']['ReportResponse'];
export type ApiJob = components['schemas']['JobResponse'];
export type ApiIncident = components['schemas']['IncidentDetailResponse'];
export type ApiFollowUp = components['schemas']['FollowUpResponse'];
export type JobReply = components['schemas']['JobAnswerRequest'];

export async function request<T>(path: string, options: RequestInit = {}, authenticated = false): Promise<T> {
  const base = import.meta.env.VITE_API_URL?.replace(/\/$/, '');
  if (!base) throw new Error('Backend service is not configured. Your report has not been submitted. No incident data is available.');
  const auth = authenticated ? await getAuthHeaders() : {};
  if (authenticated && !auth.Authorization) throw new Error('Sign in to access your private reports.');
  const response = await fetch(`${base}${path}`, {
    ...options, credentials: 'omit', cache: 'no-store',
    signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(35000)]) : AbortSignal.timeout(35000),
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...auth, ...options.headers },
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body as { message?: string; request_id?: string } | null;
    throw new Error(`${error?.message ?? `Service request failed (${response.status}).`}${error?.request_id ? ` Reference: ${error.request_id}` : ''}`);
  }
  if (response.status === 204) return undefined as T;
  if (body === null) throw new Error('The service returned an invalid response.');
  return body as T;
}

export async function uploadEvidence(file: File | Blob): Promise<string> {
  const ticket = await request<components['schemas']['UploadPrepareResponse']>('/uploads/prepare', {
    method: 'POST', body: JSON.stringify({ filename: file instanceof File ? file.name : 'voice-note',
      content_type: file.type.split(';')[0].trim(), file_size_bytes: file.size }),
  }, true);
  const url = new URL(ticket.upload_url);
  const project = new URL(import.meta.env.VITE_SUPABASE_URL);
  if (url.protocol !== 'https:' || url.origin !== project.origin || !url.pathname.startsWith('/storage/v1/object/upload/sign/')) {
    throw new Error('The service returned an invalid private upload destination.');
  }
  const response = await fetch(url, { method: 'PUT', headers: { 'Content-Type': file.type.split(';')[0].trim() },
    body: file, credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(60000) });
  if (!response.ok) throw new Error(`Private upload failed (${response.status}). Your report has not been submitted.`);
  return ticket.evidence_id;
}

export const reportApi = {
  list: (page = 1, signal?: AbortSignal) => request<ApiReport[]>(`/reports?page=${page}`, { signal }, true),
  get: (id: string, signal?: AbortSignal) => request<ApiReport>(`/reports/${encodeURIComponent(id)}`, { signal }, true),
  job: (id: string, signal?: AbortSignal) => request<ApiJob>(`/jobs/${encodeURIComponent(id)}`, { signal }, true),
  answer: (id: string, reply: JobReply) => request<ApiJob>(`/jobs/${encodeURIComponent(id)}/answers`, {
    method: 'POST', body: JSON.stringify(reply),
  }, true),
  removeMapSharing: (id: string) => request<void>(`/reports/${encodeURIComponent(id)}/map-sharing`, {
    method: 'DELETE',
  }, true),
};
