import type { Issue, IssueService } from '../../types/civic';
import { getAuthHeaders } from '../supabase/client';

function apiBase(): string {
  const url = import.meta.env.VITE_API_URL;
  if (!url) throw new Error('Backend service is not configured. No incident data is available.');
  return url.replace(/\/$/, '');
}

function readIssue(value: unknown): Issue {
  if (!value || typeof value !== 'object') throw new Error('Backend incident contract is incompatible.');
  const record = value as Record<string, unknown>;
  const coordinates = record.coordinates as Record<string, unknown> | undefined;
  if (typeof record.id !== 'string' || typeof record.title !== 'string' ||
      typeof record.category !== 'string' || typeof record.status !== 'string' ||
      !coordinates || !Number.isFinite(coordinates.lat) || !Number.isFinite(coordinates.lng)) {
    throw new Error('Backend incident contract is incompatible. API integration is required.');
  }
  return { ...(value as Issue), followUps: (value as Issue).followUps ?? [] };
}

async function mutate(path: string, body?: BodyInit, json = false): Promise<Issue> {
  const headers = await getAuthHeaders();
  if (!headers.Authorization) throw new Error('Sign in before changing a report.');
  const response = await fetch(`${apiBase()}${path}`, { method: 'POST',
    headers: { ...headers, ...(json ? { 'Content-Type': 'application/json' } : {}) }, body });
  if (!response.ok) throw new Error(`Backend request failed (${response.status}).`);
  return readIssue(await response.json());
}

export const issueService: IssueService = {
  async list(signal) {
    const response = await fetch(`${apiBase()}/incidents`, { signal, headers: await getAuthHeaders() });
    if (!response.ok) throw new Error(`Backend incident service is unavailable (${response.status}).`);
    const data: unknown = await response.json();
    if (!Array.isArray(data)) throw new Error('Backend incident contract is incompatible.');
    return { issues: data.map(readIssue), source: 'api', backendFailed: false };
  },
  toggleSupport(id) { return mutate(`/incidents/${encodeURIComponent(id)}/support`); },
  addFollowUp(id, text, photo) {
    const body = new FormData(); body.append('text', text);
    if (photo) body.append('photo', photo);
    return mutate(`/incidents/${encodeURIComponent(id)}/follow-ups`, body);
  },
  submitClarification(id, answers) {
    return mutate(`/incidents/${encodeURIComponent(id)}/clarifications`, JSON.stringify({ answers }), true);
  },
};
