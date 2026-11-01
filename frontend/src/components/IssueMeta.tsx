import type { Category, IssueStatus } from '../types/civic';
import { Icon, type IconName } from './Icon';

export const categoryIcons: Record<Category, IconName> = {
  'Garbage accumulation': 'waste',
  'Water leak': 'water',
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
      className="status-badge reported"
    >
      <span aria-hidden="true" />
      {status}
    </span>
  );
}
