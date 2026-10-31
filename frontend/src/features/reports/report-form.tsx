"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import { api, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { AudioRecorder } from "./audio-recorder";
const LocationMap = dynamic(() => import("@/components/location-map"), {
  ssr: false,
  loading: () => <p>Loading map…</p>,
});
const types = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "audio/webm",
  "audio/ogg",
  "audio/mp4",
  "audio/mpeg",
  "audio/wav",
];
export function ReportForm() {
  const [files, setFiles] = useState<File[]>([]),
    [lat, setLat] = useState(""),
    [lon, setLon] = useState("");
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [showMap, setShowMap] = useState(false);
  const validLocation =
    lat.trim() !== "" &&
    lon.trim() !== "" &&
    Number.isFinite(Number(lat)) &&
    Number.isFinite(Number(lon)) &&
    Math.abs(Number(lat)) <= 90 &&
    Math.abs(Number(lon)) <= 180;
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    if (!confirmed || !validLocation) {
      setMessage("Confirm a valid latitude and longitude.");
      return;
    }
    const data = new FormData(e.currentTarget);
    setBusy(true);
    try {
      if (files.length > 10) throw new Error("Use at most 10 attachments.");
      for (const file of files)
        if (
          !types.includes(file.type) ||
          file.size === 0 ||
          file.size > (file.type.startsWith("image/") ? 10 : 20) * 1024 * 1024
        )
          throw new Error(
            "Use supported images up to 10 MiB or audio up to 20 MiB.",
          );
      const evidence_ids: string[] = [];
      for (const file of files) {
        const upload = await api.prepare({
          mime_type: file.type as Schema["UploadPrepare"]["mime_type"],
          size_bytes: file.size,
        });
        const result = await fetch(upload.upload_url, {
          method: upload.method,
          headers: upload.headers,
          body: file,
        });
        if (!result.ok)
          throw new Error(
            "Private upload failed. Your report was not submitted.",
          );
        evidence_ids.push(upload.evidence_id);
      }
      const result = await api.report(
        {
          text: String(data.get("text") ?? ""),
          category: data.get("category") as Schema["ReportCreate"]["category"],
          location: {
            latitude: Number(lat),
            longitude: Number(lon),
            confirmed: true,
          },
          evidence_ids,
        },
        crypto.randomUUID(),
      );
      setMessage(
        `Report ${result.report_id} accepted. Processing job: ${result.job_id}.`,
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="panel space-y-6 max-w-3xl">
      <p className="text-sm">
        Private report · Only garbage accumulation and water leaks are in scope.
      </p>
      <label className="block">
        Issue category
        <select name="category">
          <option value="garbage">Garbage accumulation</option>
          <option value="water_leak">Water leak</option>
        </select>
      </label>
      <label className="block">
        What did you observe?
        <textarea
          name="text"
          rows={4}
          maxLength={10000}
          placeholder="Describe what you can see. Leave anything uncertain out."
        />
      </label>
      <label className="block">
        Photos or recorded audio
        <input
          type="file"
          multiple
          accept={types.join(",")}
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
      </label>
      <p className="text-sm">
        JPEG, PNG, WebP up to 10 MiB. WebM, Ogg, MP4 audio, MP3 or WAV up to 20
        MiB. Nothing uploads until you submit.
      </p>
      <AudioRecorder onFile={(file) => setFiles((old) => [...old, file])} />
      {files.length > 0 && (
        <ul className="text-sm">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`}>
              {f.name}{" "}
              <button
                type="button"
                className="underline ml-2"
                onClick={() =>
                  setFiles((old) => old.filter((_, index) => i !== index))
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <fieldset>
        <legend className="font-semibold">Confirm the location</legend>
        <div className="grid sm:grid-cols-2 gap-4 mt-3">
          <label>
            Latitude
            <input
              required
              type="number"
              step="any"
              min="-90"
              max="90"
              value={lat}
              onChange={(e) => {
                setLat(e.target.value);
                setConfirmed(false);
                setShowMap(false);
              }}
            />
          </label>
          <label>
            Longitude
            <input
              required
              type="number"
              step="any"
              min="-180"
              max="180"
              value={lon}
              onChange={(e) => {
                setLon(e.target.value);
                setConfirmed(false);
                setShowMap(false);
              }}
            />
          </label>
        </div>
        <label className="block mt-4">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            required
            className="mr-2"
          />
          I have checked this location.
        </label>
      </fieldset>
      <p className="text-sm">
        Loading the map shares the viewed area with the configured tile
        provider.
      </p>
      <Button
        type="button"
        variant="outline"
        disabled={!validLocation}
        onClick={() => setShowMap(true)}
      >
        Preview location on map
      </Button>
      {showMap && validLocation && (
        <LocationMap latitude={Number(lat)} longitude={Number(lon)} />
      )}
      <div>
        <Button disabled={busy} type="submit">
          {busy ? "Submitting…" : "Submit private report"}
        </Button>
      </div>
      <p role="status" aria-live="polite">
        {message}
      </p>
    </form>
  );
}
