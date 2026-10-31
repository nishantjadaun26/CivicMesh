import type { Issue, IssueService, FollowUpUpdate } from '../../types/civic';
import { getState, updateIssue, saveMedia } from './platform';
import { getAuthHeaders } from '../supabase/client';

const key = 'civicmesh.issue-support.v1';
let supportedIds: Set<string>;
try {
  const saved: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
  supportedIds = new Set(Array.isArray(saved) ? saved.filter((x): x is string => typeof x === 'string') : []);
} catch {
  supportedIds = new Set();
}

const resolve = (issue: Issue): Issue => {
  // Ensure clear separation between Authority status and Observed condition (Requirement G)
  const authorityStatus =
    issue.authorityStatus ??
    (issue.status === 'Authority Verified'
      ? 'Official inspection confirmed by municipal engineering team.'
      : issue.status === 'Resolved'
      ? 'Closed by municipal authorities following field repair.'
      : 'No official update yet. Pending municipal department inspection.');

  const observedCondition =
    issue.observedCondition ??
    (issue.extractionResult?.summary ??
      `Citizen report: ${issue.description || 'Observed by neighborhood contributor'}`);

  return {
    ...issue,
    authorityStatus,
    observedCondition,
    followUps: issue.followUps ?? [],
    supported: supportedIds.has(issue.id),
    supporters: issue.supporters - Number(issue.supported) + Number(supportedIds.has(issue.id)),
  };
};

export const issueService: IssueService = {
  async list(signal) {
    const apiUrl = import.meta.env.VITE_API_URL;
    // Attempt real backend call if configured and available
    if (apiUrl && !apiUrl.includes('localhost:8000') && !apiUrl.includes('127.0.0.1:8000')) {
      try {
        const headers = await getAuthHeaders();
        const res = await fetch(`${apiUrl}/incidents`, { signal, headers });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) return data.map(resolve);
        }
      } catch {
        // Fall back gracefully to local store
      }
    }

    await new Promise<void>((res, reject) => {
      const timer = window.setTimeout(res, 220);
      if (signal?.aborted) {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      } else {
        signal?.addEventListener(
          'abort',
          () => {
            clearTimeout(timer);
            reject(new DOMException('Aborted', 'AbortError'));
          },
          { once: true }
        );
      }
    });
    return getState().issues.map(resolve);
  },

  async toggleSupport(id) {
    const issue = getState().issues.find(i => i.id === id);
    if (!issue) throw new Error('This report is no longer available. Refresh the issue list.');
    const next = new Set(supportedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    try {
      localStorage.setItem(key, JSON.stringify([...next]));
    } catch {
      throw new Error('Your support could not be saved on this device. Please try again.');
    }
    supportedIds = next;
    const result = resolve(issue);
    updateIssue(result);
    return result;
  },

  async addFollowUp(issueId: string, text: string, photo?: File): Promise<Issue> {
    const issue = getState().issues.find(i => i.id === issueId);
    if (!issue) throw new Error('Report not found to add follow-up.');
    if (!text.trim()) throw new Error('Please provide text for the follow-up update.');

    let photoUrl: string | undefined = undefined;
    if (photo) {
      const photoId = `${issueId}-followup-${Date.now()}`;
      await saveMedia(photoId, photo);
      photoUrl = URL.createObjectURL(photo);
    }

    const followUp: FollowUpUpdate = {
      id: `FU-${Date.now()}`,
      author: 'Citizen contributor',
      text: text.trim(),
      photoUrl,
      createdAt: new Date().toISOString(),
    };

    const updatedIssue: Issue = {
      ...issue,
      followUps: [...(issue.followUps ?? []), followUp],
    };

    updateIssue(updatedIssue);
    return resolve(updatedIssue);
  },

  async submitClarification(issueId: string, answers: Record<string, string>): Promise<Issue> {
    const issue = getState().issues.find(i => i.id === issueId);
    if (!issue) throw new Error('Report not found to clarify.');

    const updatedQuestions = (issue.clarificationQuestions ?? []).map(q => ({
      ...q,
      answer: answers[q.id] ?? q.answer,
    }));

    const updatedIssue: Issue = {
      ...issue,
      clarificationQuestions: updatedQuestions,
      status: 'Under Review',
      observedCondition: `Clarified by citizen: ${Object.values(answers).filter(Boolean).join(' · ')}`,
    };

    updateIssue(updatedIssue);
    return resolve(updatedIssue);
  },
};
