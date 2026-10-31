"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
export function AudioRecorder({ onFile }: { onFile: (file: File) => void }) {
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  useEffect(
    () => () => {
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  async function start() {
    setError("");
    try {
      if (!navigator.mediaDevices || !window.MediaRecorder)
        throw new Error(
          "Audio recording is not supported here. Select an audio file instead.",
        );
      const mime = ["audio/webm", "audio/ogg", "audio/mp4"].find((m) =>
        MediaRecorder.isTypeSupported(m),
      );
      if (!mime)
        throw new Error(
          "No supported recording format. Select an audio file instead.",
        );
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const r = new MediaRecorder(stream.current, { mimeType: mime });
      recorder.current = r;
      const chunks: BlobPart[] = [];
      let size = 0;
      r.ondataavailable = (e) => {
        chunks.push(e.data);
        size += e.data.size;
        if (size > 20 * 1024 * 1024 && r.state === "recording") r.stop();
      };
      r.onstop = () => {
        stream.current?.getTracks().forEach((t) => t.stop());
        setRecording(false);
        if (size > 20 * 1024 * 1024) {
          setError("Recording exceeded 20 MiB. Please record a shorter clip.");
          return;
        }
        onFile(
          new File(chunks, `recording.${mime.split("/")[1]}`, { type: mime }),
        );
      };
      r.start(1000);
      setRecording(true);
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      setError(e instanceof Error ? e.message : "Microphone access failed.");
    }
  }
  return (
    <div>
      <Button
        type="button"
        variant="outline"
        onClick={() => (recording ? recorder.current?.stop() : void start())}
      >
        {recording ? "Stop recording" : "Record audio"}
      </Button>
      <p role="status" className="text-sm mt-2">
        {recording ? "Recording. Stop when you are finished." : error}
      </p>
    </div>
  );
}
