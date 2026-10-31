export const categories = [
  'Roads',
  'Garbage accumulation',
  'Water leak',
  'Waste',
  'Water',
  'Lighting',
  'Drainage',
  'Infrastructure',
  'Other',
] as const;

export type Category = typeof categories[number];
export type IssueStatus =
  | 'Reported'
  | 'Under Review'
  | 'CivicMesh Verified'
  | 'Authority Verified'
  | 'Resolved';

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface FollowUpUpdate {
  id: string;
  author: string;
  text: string;
  photoUrl?: string;
  createdAt: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: 'text' | 'choice' | 'location_confirm' | 'category_confirm';
  options?: string[];
  answer?: string;
}

export interface Issue {
  id: string;
  title: string;
  description: string;
  category: Category;
  status: IssueStatus;
  location: string;
  coordinates: Coordinates;
  reportedAt: string;
  reporter: string;
  supporters: number;
  supported: boolean;
  photoUrl?: string;
  authorId: string;
  photoId?: string;
  audioId?: string;
  campaignId?: string;
  evidenceConsent?: boolean;
  // Requirement G: Separate authority status from observed condition
  authorityStatus?: string; // Official municipal/authority updates
  observedCondition?: string; // Citizen observations / AI assessment
  followUps?: FollowUpUpdate[];
  clarificationQuestions?: ClarificationQuestion[];
  jobId?: string;
  extractionResult?: {
    confidence: number;
    detectedCategory: string;
    summary: string;
    suggestedUrgency: 'low' | 'medium' | 'high' | 'critical';
  };
}

export interface IssueService {
  list(signal?: AbortSignal): Promise<Issue[]>;
  toggleSupport(id: string): Promise<Issue>;
  addFollowUp(issueId: string, text: string, photo?: File): Promise<Issue>;
  submitClarification(
    issueId: string,
    answers: Record<string, string>
  ): Promise<Issue>;
}

export const DEMO_CENTER: Coordinates = { lat: 12.9784, lng: 77.6408 };
