import type { Issue } from '../../types/civic';
import { request, type ApiIncident } from './client';

function readIncident(item: ApiIncident): Issue {
  if (!item?.id || !['garbage', 'water_leak'].includes(item.category) || !Number.isFinite(item.latitude) || !Number.isFinite(item.longitude)) {
    throw new Error('The service returned an incompatible incident record.');
  }
  return { id: item.id, title: item.category === 'garbage' ? 'Garbage accumulation' : 'Water leak',
    category: item.category === 'garbage' ? 'Garbage accumulation' : 'Water leak',
    description: item.observed_condition, observedCondition: item.observed_condition,
    authorityStatus: item.authority_status, status: 'Reported', coordinates: { lat: item.latitude, lng: item.longitude },
    location: `${item.latitude.toFixed(5)}, ${item.longitude.toFixed(5)}`, reportedAt: item.created_at };
}

export const issueService = {
  async list(signal?: AbortSignal, page = 1) {
    const items = await request<ApiIncident[]>(`/incidents?page=${page}&limit=20`, { signal });
    if (!Array.isArray(items)) throw new Error('The service returned an incompatible incident list.');
    return { issues: items.map(readIncident), source: 'api' as const, backendFailed: false };
  },
  async get(id: string, signal?: AbortSignal) {
    return readIncident(await request<ApiIncident>(`/incidents/${encodeURIComponent(id)}`, { signal }));
  },
};
