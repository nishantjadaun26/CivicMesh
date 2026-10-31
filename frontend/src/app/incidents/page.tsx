import { IncidentView } from "@/features/incidents/incident-view";
export default function Page() {
  return (
    <>
      <p className="eyebrow">Shared neighbourhood evidence</p>
      <h1 className="text-4xl font-semibold mt-3 mb-4">Incidents</h1>
      <p className="mb-8">
        Only approved public information appears here. Citizen observations are
        not authority confirmations.
      </p>
      <IncidentView />
    </>
  );
}
