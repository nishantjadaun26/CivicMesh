import type { Category, IssueStatus } from '../types/civic';
import { Icon, type IconName } from './Icon';

export const categoryIcons: Record<Category, IconName> = {
  Roads: 'road',
  'Garbage accumulation': 'waste',
  'Water leak': 'water',
  Waste: 'waste',
  Water: 'water',
  Lighting: 'light',
  Drainage: 'drain',
  Infrastructure: 'road',
  Other: 'pin',
};

export function CategoryIcon({ category }: { category: Category }) {
  const normalizedClass = category.toLowerCase().replace(/\s+/g, '-');
  return (
    <span className={`category-icon category-${normalizedClass}`}>
      <Icon name={categoryIcons[category] ?? 'pin'} />
    </span>
  );
}

export function StatusBadge({ status }: { status: IssueStatus }) {
  return (
    <span
      className={`status-badge ${
        status === 'Reported'
          ? 'reported'
          : status === 'Under Review'
          ? 'confirmed'
          : 'resolved'
      }`}
    >
      <span aria-hidden="true" />
      {status}
    </span>
  );
}
