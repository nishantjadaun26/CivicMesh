import { ReportForm } from "@/features/reports/report-form";
export default function Page() {
  return (
    <>
      <p className="eyebrow">Your observation matters</p>
      <h1 className="text-4xl font-semibold mt-3 mb-4">Report an issue</h1>
      <p className="mb-8 max-w-2xl">
        Sign in before submitting. Report persistence and processing are not yet
        implemented; the service will explain what is unavailable.
      </p>
      <ReportForm />
    </>
  );
}
