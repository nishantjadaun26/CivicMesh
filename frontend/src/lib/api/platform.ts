import { useSyncExternalStore } from 'react';
import type { Coordinates, Category, Issue } from '../../types/civic';
import { getAuthHeaders, getCurrentUser } from '../supabase/client';

export interface User {
  id: string;
  name: string;
  username: string;
  joined: string;
}

export interface Campaign {
  id: string;
  title: string;
  description: string;
  category: Category;
  location: string;
  joined: boolean;
  followers: string[];
  updatedAt: string;
}

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
  idempotencyKey?: string;
}

export interface Contribution {
  id: string;
  title: string;
  date: string;
  points: number;
  reason: string;
  issueId?: string;
}

export interface Evidence {
  id: string;
  blob: Blob;
  visibility: 'report-only' | 'campaign';
}

interface State {
  issues: Issue[];
  campaigns: Campaign[];
}

// Operational data is loaded only from configured services. Ignore previous demo caches.
let state: State = { issues: [], campaigns: [] };

const listeners = new Set<()=>void>();
function commit(next: State) {
  state = next;
  listeners.forEach(fn => fn());
}

export const getState = () => state;
export function useAppData() {
  return useSyncExternalStore(fn => {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }, getState);
}

export const guestUser: User = { id: '', name: 'Guest', username: '', joined: '' };
export const contributions: Contribution[] = [];

function db() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const r = indexedDB.open('civicmesh-media', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('media');
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(new Error('Media storage is unavailable. Check browser storage permissions.'));
  });
}

export async function saveMedia(id: string, blob: Blob) {
  const database = await db();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = database.transaction('media', 'readwrite');
      tx.objectStore('media').put(blob, id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(new Error('Could not save the attachment. Try a smaller file.'));
    });
  } finally {
    database.close();
  }
}

export async function readMedia(id: string) {
  const database = await db();
  try {
    return await new Promise<Blob | undefined>((resolve, reject) => {
      const r = database.transaction('media').objectStore('media').get(id);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
  } finally {
    database.close();
  }
}

export interface SubmissionProcessingStatus {
  step: 1 | 2 | 3 | 4 | 5 | 6;
  message: string;
  jobId?: string;
  reportId?: string;
  isBackendConnected: boolean;
}

export interface CitizenService {
  createReport(
    draft: ReportDraft,
    onProgress?: (status: SubmissionProcessingStatus) => void
  ): Promise<Issue>;
  toggleCampaign(id: string): Promise<void>;
}

export function getUserCampaignMemberships(userId: string): Set<string> {
  try {
    const raw = localStorage.getItem(`civicmesh.campaign-membership.${userId}`);
    if (raw) return new Set(JSON.parse(raw));
    return new Set();
  } catch {
    return new Set();
  }
}

export function setUserCampaignMemberships(userId: string, ids: Set<string>): void {
  try {
    localStorage.setItem(`civicmesh.campaign-membership.${userId}`, JSON.stringify([...ids]));
  } catch {
    throw new Error(
      'Your campaign membership could not be saved. Free some browser storage and try again.'
    );
  }
}

export const citizenService: CitizenService = {
  async createReport(draft, onProgress) {
    if (!import.meta.env.VITE_API_URL) throw new Error('Backend service is not configured. Your report has not been submitted.');
    if (!draft.photo) throw new Error('Add a photograph before submitting.');

    if (!draft.idempotencyKey) {
      draft.idempotencyKey = crypto.randomUUID();
    }
    const idempotencyKey = draft.idempotencyKey;
    const apiUrl = import.meta.env.VITE_API_URL;
    const currentUser = await getCurrentUser();
    if (!currentUser) throw new Error('Sign in before submitting a private report.');
    const reporterName = currentUser.email?.split('@')[0] ?? 'Citizen';
    const authorId = currentUser.id;

    if (apiUrl) {
      onProgress?.({
        step: 1,
        message: 'Requesting authorized upload ticket…',
        isBackendConnected: true,
      });

      const filesToAuthorize: { file: File | Blob; name: string; type: string; size: number }[] = [
        { file: draft.photo, name: draft.photo.name, type: draft.photo.type, size: draft.photo.size },
        ...(draft.audio ? [{ file: draft.audio, name: 'voice-note.webm', type: draft.audio.type, size: draft.audio.size }] : []),
      ];

      const authHeaders = await getAuthHeaders();
      const uploadAuthRes = await fetch(`${apiUrl}/uploads/authorize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
          ...authHeaders,
        },
        body: JSON.stringify({
          files: filesToAuthorize.map(f => ({ name: f.name, type: f.type, size: f.size })),
        }),
      });

      if (!uploadAuthRes.ok) {
        throw new Error(`Upload authorization failed (${uploadAuthRes.status}): ${await uploadAuthRes.text()}`);
      }

      const authData = await uploadAuthRes.json();
      const uploadedEvidenceIds: string[] = [];

      const tickets = authData.tickets || authData.files || [];
      if (!Array.isArray(tickets) || tickets.length !== filesToAuthorize.length) {
        throw new Error('Upload authorization returned an invalid or incomplete ticket list.');
      }

      for (let i = 0; i < tickets.length; i++) {
        const ticket = tickets[i];
        const item = filesToAuthorize[i];

        if (!ticket.id || !ticket.uploadUrl || !item.file) {
          throw new Error(`Incomplete upload ticket at index ${i}. Ticket ID and upload URL are required.`);
        }

        const putRes = await fetch(ticket.uploadUrl, {
          method: 'PUT',
          headers: ticket.headers || { 'Content-Type': item.type },
          body: item.file,
        });

        if (!putRes.ok) {
          throw new Error(`Failed to upload media file ${item.name} (${putRes.status}): ${await putRes.text()}`);
        }

        uploadedEvidenceIds.push(ticket.id);
      }

      onProgress?.({
        step: 2,
        message: 'Evidence files uploaded.',
        isBackendConnected: true,
      });

      onProgress?.({
        step: 3,
        message: 'Submitting civic report to backend workflow…',
        isBackendConnected: true,
      });

      const reportRes = await fetch(`${apiUrl}/reports`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
          ...authHeaders,
        },
        body: JSON.stringify({
          title: draft.title.trim() || `${draft.category} issue near ${draft.location}`,
          description: draft.description.trim(),
          category: draft.category,
          location: draft.location,
          coordinates: draft.coordinates,
          campaignId: draft.campaignId,
          evidenceConsent: draft.evidenceConsent,
          evidenceIds: uploadedEvidenceIds,
        }),
      });

      if (!reportRes.ok) {
        throw new Error(`Report submission failed (${reportRes.status}): ${await reportRes.text()}`);
      }

      const reportData = await reportRes.json();
      const backendReportId = reportData.report_id || reportData.id;
      const backendJobId = reportData.job_id || reportData.jobId;
      if (!backendReportId || !backendJobId) throw new Error('Backend response did not include a report ID and processing job.');

      onProgress?.({
        step: 4,
        message: 'Report received. Extraction job queued…',
        reportId: backendReportId,
        jobId: backendJobId ?? undefined,
        isBackendConnected: true,
      });

      onProgress?.({
        step: 5,
        message: 'Awaiting processing status from the backend…',
        reportId: backendReportId,
        jobId: backendJobId ?? undefined,
        isBackendConnected: true,
      });

      try {
        await saveMedia(backendReportId + '-photo', draft.photo);
        if (draft.audio) await saveMedia(backendReportId + '-audio', draft.audio);
      } catch {
        // Local cache error does not duplicate report
      }

      const issue: Issue = {
        id: backendReportId,
        title: reportData.title || draft.title.trim() || `${draft.category} issue near ${draft.location}`,
        description: reportData.description || draft.description.trim(),
        category: reportData.category || draft.category,
        location: reportData.location || draft.location,
        coordinates: reportData.coordinates || draft.coordinates,
        photoId: backendReportId + '-photo',
        audioId: draft.audio ? backendReportId + '-audio' : undefined,
        evidenceConsent: draft.evidenceConsent,
        campaignId: draft.campaignId,
        status: reportData.status || 'Reported',
        reporter: reportData.reporter || reporterName,
        authorId: reportData.authorId || authorId,
        reportedAt: reportData.reportedAt || reportData.created_at || new Date().toISOString(),
        supporters: reportData.supporters || 0,
        supported: Boolean(reportData.supported),
        jobId: backendJobId,
        authorityStatus: reportData.authorityStatus,
        observedCondition: reportData.observedCondition || draft.description.trim(),
        extractionResult: reportData.extractionResult,
        clarificationQuestions: reportData.clarificationQuestions,
      };

      onProgress?.({
        step: 6,
        message: 'Report received and queued by backend.',
        reportId: issue.id,
        jobId: issue.jobId,
        isBackendConnected: true,
      });

      commit({ ...state, issues: [issue, ...state.issues] });
      return issue;
    }

    throw new Error('Backend service is unavailable. Your report has not been submitted.');
  },

  async toggleCampaign(_id) {
    throw new Error('Campaign participation is not implemented yet.');
  },
};

export function updateIssue(issue: Issue) {
  commit({
    ...state,
    issues: state.issues.map(i => (i.id === issue.id ? issue : i)),
  });
}
