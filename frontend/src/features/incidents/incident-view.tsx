"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
export function IncidentView({ id }: { id?: string }) {
  const [items, setItems] = useState<Schema["Incident"][] | null>(null),
    [error, setError] = useState(""),
    [cursor, setCursor] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const work = id
      ? api.incident(id).then((item) => ({ items: [item], next_cursor: null }))
      : api.incidents();
    work
      .then((page) => {
        if (active) {
          setItems(page.items);
          setCursor(page.next_cursor ?? null);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, retry]);
  async function more() {
    if (!cursor) return;
    setBusy(true);
    try {
      const page = await api.incidents(cursor);
      setItems((old) => [...(old ?? []), ...page.items]);
      setCursor(page.next_cursor ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load incidents.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-live="polite">
      {error && (
        <div role="alert" className="panel">
          <p>{error}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => setRetry((n) => n + 1)}
          >
            Retry
          </Button>
        </div>
      )}
      {!items && !error && <p>Loading incidents…</p>}
      {items?.length === 0 && (
        <div className="panel">
          <h2 className="text-xl">No published incidents yet</h2>
          <p className="mt-3">
            Approved incidents will appear here when genuine reports have been
            processed.
          </p>
        </div>
      )}
      <div className="grid gap-4">
        {items?.map((item) => (
          <article className="panel" key={item.incident_id}>
            <p className="eyebrow">{item.category.replace("_", " ")}</p>
            <h2 className="text-xl my-3">
              {id ? (
                item.public_summary
              ) : (
                <Link
                  className="underline"
                  href={`/incidents/${item.incident_id}`}
                >
                  {item.public_summary}
                </Link>
              )}
            </h2>
            <dl className="grid sm:grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="font-semibold">Authority status</dt>
                <dd>{item.authority_status.replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt className="font-semibold">Observed condition</dt>
                <dd>
                  {item.observed_condition?.replaceAll("_", " ") ??
                    "Not assessed"}
                </dd>
              </div>
            </dl>
            <p className="text-xs mt-4">
              Created {new Date(item.created_at).toLocaleString()}
            </p>
          </article>
        ))}
      </div>
      {cursor && (
        <Button disabled={busy} onClick={() => void more()} className="mt-5">
          {busy ? "Loading…" : "Load more"}
        </Button>
      )}
    </section>
  );
}
