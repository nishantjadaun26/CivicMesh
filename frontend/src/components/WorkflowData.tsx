/** Render untrusted observations as escaped text, with no HTML or executable links. */
export function WorkflowData({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>Unknown</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><WorkflowData value={item} /></li>)}</ul> : <span>None supplied</span>;
  if (typeof value === 'object') return <dl className="workflow-data">{Object.entries(value).map(([key, item]) => <div key={key}>
    <dt>{key.replaceAll('_', ' ')}</dt><dd><WorkflowData value={item} /></dd></div>)}</dl>;
  return <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{String(value)}</span>;
}
