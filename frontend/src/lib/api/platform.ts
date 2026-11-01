import { useSyncExternalStore } from 'react';
import type { Coordinates, Category, Issue } from '../../types/civic';
import { seedIssues } from '../mocks/issues';
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

const seeds: Campaign[] = [
  {
    id: 'safer-streets',
    title: 'A safer walk to school',
    description:
      'Neighbors are documenting damaged roads and uneven pavements around the school routes. Add a related report to help build a clear picture of the problem.',
    category: 'Roads',
    location: 'Indiranagar school routes',
    joined: false,
    followers: ['neighbor-1', 'neighbor-5'],
    updatedAt: '2026-10-31',
  },
  {
    id: 'clean-corners',
    title: 'Clean corners, shared responsibility',
    description:
      'A neighborhood effort to document recurring waste accumulation and share cleanup updates.',
    category: 'Garbage accumulation',
    location: '100 Feet Road and nearby parks',
    joined: false,
    followers: ['me', 'neighbor-2'],
    updatedAt: '2026-10-30',
  },
  {
    id: 'rain-ready',
    title: 'Keep our streets rain-ready',
    description:
      'Bring together reports of waterlogging and blocked drains before the next heavy rain.',
    category: 'Water leak',
    location: 'HAL 2nd Stage',
    joined: false,
    followers: ['neighbor-3', 'neighbor-4'],
    updatedAt: '2026-10-29',
  },
];

seedIssues.forEach(i => {
  i.campaignId =
    i.category === 'Roads'
      ? 'safer-streets'
      : i.category === 'Waste' || i.category === 'Garbage accumulation'
      ? 'clean-corners'
      : i.category === 'Water' || i.category === 'Drainage' || i.category === 'Water leak'
      ? 'rain-ready'
      : undefined;
  if (!i.observedCondition) {
    i.observedCondition = `Citizen report: ${i.description || 'Observed by neighborhood contributor'}`;
  }
});

const key = 'civicmesh.app.v1';
let state: State = { issues: seedIssues, campaigns: seeds };
try {
  const saved = JSON.parse(localStorage.getItem(key) ?? 'null');
  if (
    saved &&
    Array.isArray(saved.issues) &&
    Array.isArray(saved.campaigns) &&
    saved.issues.every((i: Issue) => i.id && i.coordinates && i.category)
  ) {
    state = saved;
  }
} catch {
  /* Use coherent seed data when storage is unavailable or corrupt. */
}

const listeners = new Set<()=>void>();
function commit(next: State) {
  try {
    localStorage.setItem(key, JSON.stringify(next));
  } catch {
    throw new Error('Your changes could not be saved. Free some browser storage and try again.');
  }
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

export const demoUser: User = {
  id: 'me',
  name: 'Meera Krishnan',
  username: 'meera.indiranagar',
  joined: 'October 2026',
};

export const contributions: Contribution[] = [
  {
    id: 'cleanup',
    title: 'Shared a neighborhood cleanup update',
    date: '2026-10-27',
    points: 20,
    reason: 'Helpful follow-up evidence reviewed in this demo.',
    issueId: 'CM-1037',
  },
  {
    id: 'context',
    title: 'Added useful location context',
    date: '2026-10-30',
    points: 10,
    reason: 'Clear, actionable location details in this demo.',
    issueId: 'CM-1040',
  },
];

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
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

export function setUserCampaignMemberships(userId: string, ids: Set<string>): void {
  try {
    localStorage.setItem(`civicmesh.campaign-membership.${userId}`, JSON.stringify([...ids]));
  } catch {
    // browser storage unavailable
  }
}

export const citizenService: CitizenService = {
  async createReport(draft, onProgress) {
    if (!draft.photo) throw new Error('Add a photograph before submitting.');

    if (!draft.idempotencyKey) {
      draft.idempotencyKey = crypto.randomUUID();
    }
    const idempotencyKey = draft.idempotencyKey;
    const apiUrl = import.meta.env.VITE_API_URL;
    const currentUser = await getCurrentUser();
    const reporterName = currentUser?.email ? currentUser.email.split('@')[0] : demoUser.name;
    const authorId = currentUser ? currentUser.id : 'me';

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
        message: 'Uploading encrypted evidence media…',
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
      const backendReportId = reportData.report_id || reportData.id || `CM-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
      const backendJobId = reportData.job_id || reportData.jobId;

      onProgress?.({
        step: 4,
        message: 'Report received. Extraction job queued…',
        reportId: backendReportId,
        jobId: backendJobId ?? undefined,
        isBackendConnected: true,
      });

      onProgress?.({
        step: 5,
        message: 'Extracting incident data via AI verification workflow…',
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

    // Unconfigured backend branch: save report on device only
    onProgress?.({
      step: 1,
      message: 'Saving report locally on this device…',
      isBackendConnected: false,
    });

    const id = `CM-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
    await saveMedia(id + '-photo', draft.photo);
    if (draft.audio) await saveMedia(id + '-audio', draft.audio);

    onProgress?.({
      step: 6,
      message: 'Saved on this device only.',
      reportId: id,
      isBackendConnected: false,
    });

    const issue: Issue = {
      id,
      title: draft.title.trim() || `${draft.category} issue near ${draft.location}`,
      description: draft.description.trim(),
      category: draft.category,
      location: draft.location,
      coordinates: draft.coordinates,
      photoId: id + '-photo',
      audioId: draft.audio ? id + '-audio' : undefined,
      evidenceConsent: draft.evidenceConsent,
      campaignId: draft.campaignId,
      status: 'Reported',
      reporter: reporterName,
      authorId: authorId,
      reportedAt: new Date().toISOString(),
      supporters: 0,
      supported: false,
      authorityStatus: undefined,
      observedCondition: draft.description.trim() || 'Saved on this device only',
    };

    commit({ ...state, issues: [issue, ...state.issues] });
    return issue;
  },

  async toggleCampaign(id) {
    const currentUser = await getCurrentUser();
    const userId = currentUser ? currentUser.id : demoUser.id;

    const memberships = getUserCampaignMemberships(userId);
    const wasJoined = memberships.has(id);
    if (wasJoined) {
      memberships.delete(id);
    } else {
      memberships.add(id);
    }
    setUserCampaignMemberships(userId, memberships);

    commit({
      ...state,
      campaigns: state.campaigns.map(c =>
        c.id === id ? { ...c, joined: !c.joined } : c
      ),
    });
  },
};

export function updateIssue(issue: Issue) {
  commit({
    ...state,
    issues: state.issues.map(i => (i.id === issue.id ? issue : i)),
  });
}
