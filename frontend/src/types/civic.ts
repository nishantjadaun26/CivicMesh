export const categories = ['Garbage accumulation', 'Water leak'] as const;
export type Category = typeof categories[number];
export type IssueStatus = 'Reported' | 'Under Review' | 'CivicMesh Verified' | 'Authority Verified' | 'Resolved';
export interface Coordinates { lat: number; lng: number; }
export interface Issue {
  id: string; title: string; description: string; category: Category; status: IssueStatus;
  location: string; coordinates: Coordinates; reportedAt: string;
  authorityStatus: string; observedCondition: string;
}
// Viewport only. A citizen must explicitly confirm the incident coordinates.
export const MAP_CENTER: Coordinates = { lat: 0, lng: 0 };
