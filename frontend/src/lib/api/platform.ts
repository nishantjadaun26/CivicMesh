import { useSyncExternalStore } from 'react';
import type { Coordinates, Category } from '../../types/civic';
import { request, uploadEvidence, type ApiReport } from './client';
import { getCurrentUser } from '../supabase/client';

export interface Campaign { id: string; title: string; description: string; category: Category;
  location: string; joined: boolean; followers: string[]; updatedAt: string; }
export interface ReportDraft {
  title: string;
  description: string;
  category: Category;
  location: string;
  coordinates: Coordinates;
  photo?: File;
  audio?: Blob;
  campaignId?: string;
  evidenceConsent: boolean;
  shareOnMap: boolean;
  idempotencyKey?: string;
}


const empty = { campaigns: [] as Campaign[] };
export function useAppData() { return useSyncExternalStore(() => () => {}, () => empty); }
export interface SubmissionProcessingStatus { step: number; message: string; isBackendConnected: boolean; }
const submittedEvidence = new WeakMap<ReportDraft, { photo: File; audio?: Blob; ids: string[] }>();
const submittedPayloads = new WeakMap<ReportDraft, string>();

export const citizenService = {
  async createReport(draft: ReportDraft, onProgress?: (value: SubmissionProcessingStatus) => void): Promise<ApiReport> {
    if (!import.meta.env.VITE_API_URL) throw new Error('Backend service is not configured. Your report has not been submitted.');
    if (!await getCurrentUser()) throw new Error('Sign in before submitting a private report.');
    if (!draft.photo) throw new Error('Add a photograph before submitting.');
    if (draft.photo.size + (draft.audio?.size ?? 0) > 12 * 1024 * 1024) throw new Error('Combined attachments must not exceed 12 MiB.');
    let saved = submittedEvidence.get(draft);
    if (!saved || saved.photo !== draft.photo || saved.audio !== draft.audio) {
      onProgress?.({ step: 1, message: 'Uploading private evidence…', isBackendConnected: true });
      const ids = [await uploadEvidence(draft.photo)];
      if (draft.audio) ids.push(await uploadEvidence(draft.audio));
      saved = { photo: draft.photo, audio: draft.audio, ids };
      submittedEvidence.set(draft, saved);
    }
    const payload = JSON.stringify({
      text: [draft.title.trim(), draft.description.trim(), draft.location.trim()].filter(Boolean).join('\n'),
      public_summary: draft.shareOnMap
        ? [draft.title.trim(), draft.description.trim()].filter(Boolean).join('\n')
        : '',
      share_on_map: draft.shareOnMap,
      category: draft.category === 'Water leak' ? 'water_leak' : 'garbage',
      location: { latitude: draft.coordinates.lat, longitude: draft.coordinates.lng, confirmed: true },
      evidence_ids: saved.ids,
    });
    if (!draft.idempotencyKey || submittedPayloads.get(draft) !== payload) draft.idempotencyKey = crypto.randomUUID();
    submittedPayloads.set(draft, payload);
    onProgress?.({ step: 2, message: 'Submitting report…', isBackendConnected: true });
    return request<ApiReport>('/reports', { method: 'POST', body: payload,
      headers: { 'Idempotency-Key': draft.idempotencyKey } }, true);
  },
};
