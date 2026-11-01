import type { Issue, IssueService, IssueListResult, FollowUpUpdate } from '../../types/civic';
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
  // Preserve explicitly provided authorityStatus, leaving it undefined when absent (Requirement G)
  const authorityStatus = issue.authorityStatus;

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

// Backend-response helper: applies observedCondition and followUps defaults without local supportedIds overlay
const resolveBackendIssue = (issue: Issue): Issue => {
  return {
    ...issue,
    observedCondition:
      issue.observedCondition ??
      (issue.extractionResult?.summary ??
        `Citizen report: ${issue.description || 'Observed by neighborhood contributor'}`),
    followUps: issue.followUps ?? [],
  };
};

export const issueService: IssueService = {
  async list(signal): Promise<IssueListResult> {
    const apiUrl = import.meta.env.VITE_API_URL;
    let backendFailed = false;

    // Attempt real backend call if configured and available
    if (apiUrl) {
      try {
        const headers = await getAuthHeaders();
        const res = await fetch(`${apiUrl}/incidents`, { signal, headers });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            return {
              issues: data.map(resolveBackendIssue),
              source: 'api',
              backendFailed: false,
            };
          }
        } else {
          backendFailed = true;
        }
      } catch (err) {
        if (signal?.aborted) throw err;
        backendFailed = true;
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

    return {
      issues: getState().issues.map(resolve),
      source: 'local',
      backendFailed,
    };
  },

  async toggleSupport(id) {
    const apiUrl = import.meta.env.VITE_API_URL;
    if (apiUrl) {
      const headers = await getAuthHeaders();
      const res = await fetch(`${apiUrl}/incidents/${id}/support`, {
        method: 'POST',
        headers: { ...headers },
      });
      if (!res.ok) {
        throw new Error(`Failed to toggle support (${res.status}): ${await res.text()}`);
      }
      const updated = await res.json();
      return resolveBackendIssue(updated);
    }

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
    const apiUrl = import.meta.env.VITE_API_URL;
    if (apiUrl) {
      const headers = await getAuthHeaders();
      const formData = new FormData();
      formData.append('text', text);
      if (photo) formData.append('photo', photo);
      const res = await fetch(`${apiUrl}/incidents/${issueId}/follow-ups`, {
        method: 'POST',
        headers: { ...headers },
        body: formData,
      });
      if (!res.ok) {
        throw new Error(`Failed to submit follow-up (${res.status}): ${await res.text()}`);
      }
      const updated = await res.json();
      return resolveBackendIssue(updated);
    }

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
    const apiUrl = import.meta.env.VITE_API_URL;
    if (apiUrl) {
      const headers = await getAuthHeaders();
      const res = await fetch(`${apiUrl}/incidents/${issueId}/clarifications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) {
        throw new Error(`Failed to submit clarification (${res.status}): ${await res.text()}`);
      }
      const updated = await res.json();
      return resolveBackendIssue(updated);
    }

    const issue = getState().issues.find(i => i.id === issueId);
    if (!issue) throw new Error('Report not found to clarify.');

    const updatedQuestions = (issue.clarificationQuestions ?? []).map(q => ({
      ...q,
      answer: answers[q.id] ?? q.answer,
    }));

    const clarifiedDetails = Object.entries(answers)
      .filter(([_, ans]) => Boolean(ans?.trim()))
      .map(([qid, ans]) => {
        const qText = issue.clarificationQuestions?.find(q => q.id === qid)?.question;
        return qText ? `${qText}: ${ans}` : ans;
      })
      .join('; ');

    const newObservedCondition = clarifiedDetails
      ? (issue.observedCondition ? `${issue.observedCondition} [Clarification: ${clarifiedDetails}]` : clarifiedDetails)
      : issue.observedCondition;

    const updatedIssue: Issue = {
      ...issue,
      clarificationQuestions: updatedQuestions,
      status: issue.status,
      observedCondition: newObservedCondition,
    };

    updateIssue(updatedIssue);
    return resolve(updatedIssue);
  },
};
