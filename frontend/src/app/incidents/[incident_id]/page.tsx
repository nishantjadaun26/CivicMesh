import { IncidentView } from "@/features/incidents/incident-view";
export default async function Page({
  params,
}: {
  params: Promise<{ incident_id: string }>;
}) {
  const { incident_id } = await params;
  return (
    <>
      <h1 className="text-4xl font-semibold mb-8">Incident details</h1>
      <IncidentView id={incident_id} />
    </>
  );
}
