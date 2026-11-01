import type { components } from './api.generated';
export const categories = ['Garbage accumulation', 'Water leak'] as const;
export type Category = typeof categories[number];
export type IssueStatus = 'Community report · unverified' | 'Published observation';
export interface Coordinates { lat: number; lng: number; }
export interface Issue {
  id: string; title: string; description: string; category: Category; status: IssueStatus;
  location: string; coordinates: Coordinates; reportedAt: string;
  timeline: components['schemas']['StatusEventResponse'][];
  authorityStatus: string; observedCondition: string;
}
// Viewport only. A citizen must explicitly confirm the incident coordinates.
export const MAP_CENTER: Coordinates = { lat: 0, lng: 0 };
