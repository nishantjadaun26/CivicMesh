import Link from "next/link";
import { ArrowUpRight, Camera, MapPin, FileCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
export default function Home() {
  return (
    <>
      <p className="eyebrow">Neighbourhood action, grounded in evidence</p>
      <section className="grid md:grid-cols-[1.5fr_1fr] gap-12 py-8">
        <div>
          <h1 className="text-5xl md:text-7xl tracking-tight font-semibold leading-[1.06]">
            A shared voice.
            <br />
            <span className="text-teal-700">A clearer picture.</span>
          </h1>
          <p className="text-lg mt-7 max-w-xl leading-relaxed text-teal-950/70">
            Document garbage accumulation or a water leak. Help turn individual
            observations into shared incidents with evidence that can be
            followed up.
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Button asChild>
              <Link href="/reports">
                Report an issue <ArrowUpRight size={18} className="ml-3" />
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/incidents">View incidents</Link>
            </Button>
          </div>
        </div>
        <aside className="panel self-end">
          <p className="eyebrow">Foundation preview</p>
          <h2 className="text-2xl mt-3">Start with what you know.</h2>
          <p className="leading-relaxed mt-4">
            Reports and media stay private. The public incident view will show
            only approved information.
          </p>
          <p className="mt-4 text-sm text-teal-900/70">
            Submission and AI processing are still being connected. No
            operational reports or results are preloaded.
          </p>
        </aside>
      </section>
      <section
        className="grid md:grid-cols-3 gap-5 mt-8"
        aria-label="How it works"
      >
        {[
          {
            Icon: Camera,
            title: "Capture the evidence",
            text: "Add your own photo, text, or recorded Hindi or English audio.",
          },
          {
            Icon: MapPin,
            title: "Confirm the location",
            text: "Check the exact place yourself. Missing details stay unknown.",
          },
          {
            Icon: FileCheck,
            title: "Follow the evidence",
            text: "Citizen observations remain distinct from verified authority responses.",
          },
        ].map(({ Icon, title, text }) => (
          <article className="panel" key={title}>
            <Icon aria-hidden="true" className="mb-5 text-teal-700" />
            <h2 className="font-semibold text-lg">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-teal-950/70">
              {text}
            </p>
          </article>
        ))}
      </section>
    </>
  );
}
