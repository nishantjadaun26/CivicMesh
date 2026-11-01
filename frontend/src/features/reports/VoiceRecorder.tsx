import { useEffect, useRef, useState } from 'react';

export interface VoiceRecorderProps {
  value?: Blob;
  onChange: (blob: Blob | undefined) => void;
}

export function VoiceRecorder({ value, onChange }: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');

  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const alive = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(timer.current);
      if (recorder.current?.state === 'recording') recorder.current.stop();
      stream.current?.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    if (!value) {
      setUrl('');
      setFileName('');
      return;
    }
    const objectUrl = URL.createObjectURL(value);
    setUrl(objectUrl);
    setFileName(value instanceof File ? value.name : 'Recorded audio note');
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [value]);

  async function start() {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Recording is unsupported in this browser. You can upload an audio file below or use the text description.');
      return;
    }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) {
        s.getTracks().forEach(t => t.stop());
        return;
      }
      stream.current = s;
      const r = new MediaRecorder(s);
      recorder.current = r;
      const chunks: BlobPart[] = [];
      r.ondataavailable = e => {
        if (e.data.size) chunks.push(e.data);
      };
      r.onstop = () => {
        s.getTracks().forEach(t => t.stop());
        clearTimeout(timer.current);
        if (!alive.current) return;
        const blob = new Blob(chunks, { type: r.mimeType || 'audio/webm' });
        onChange(blob);
        setRecording(false);
      };
      r.start();
      setRecording(true);
      timer.current = setTimeout(() => {
        if (r.state === 'recording') r.stop();
      }, 60000);
    } catch {
      setError('Microphone access was unavailable. Please upload an audio file or use the text description instead.');
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    setError('');
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate audio size (max 10 MiB)
    if (file.size > 10 * 1024 * 1024) {
      setError('Audio file must be smaller than 10 MiB.');
      e.target.value = '';
      return;
    }

    // Validate audio type
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/webm', 'audio/ogg'];
    if (!validTypes.includes(file.type.split(';')[0].trim())) {
      setError('Choose MP3, WAV, MP4, WebM or Ogg audio. Other audio formats are not supported.');
      e.target.value = '';
      return;
    }

    onChange(file);
  }

  function clearAudio() {
    if (url) URL.revokeObjectURL(url);
    setUrl('');
    setFileName('');
    onChange(undefined);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  return (
    <div className="voice-control">
      <h3>
        Voice description <span>(optional)</span>
      </h3>
      <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '4px 0 10px', lineHeight: '1.5' }}>
        Record a spoken note, or choose an existing audio file if microphone access is unavailable.
      </p>

      {!url && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          {recording ? (
            <button type="button" className="secondary-button" onClick={() => recorder.current?.stop()}>
              Stop recording
            </button>
          ) : (
            <button type="button" className="secondary-button" onClick={start}>
              Record voice note
            </button>
          )}

          <button
            type="button"
            className="secondary-button"
            onClick={() => fileInputRef.current?.click()}
          >
            Choose audio file
          </button>
          <input
            ref={fileInputRef}
            type="file"
            tabIndex={-1}
            accept="audio/mpeg,audio/wav,audio/mp4,audio/webm,audio/ogg,.mp3,.wav,.mp4,.webm,.ogg"
            aria-label="Upload audio file"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </div>
      )}

      {recording && (
        <p role="status" style={{ fontSize: '12px', color: 'var(--accent)', marginTop: '8px' }}>
          Recording… Stops automatically after 60 seconds.
        </p>
      )}

      {url && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ink)', marginBottom: '4px' }}>
            {fileName}
          </div>
          <audio controls src={url} style={{ width: '100%', maxWidth: '400px' }} />
          <button type="button" className="text-button" onClick={clearAudio} style={{ display: 'block', marginTop: '6px' }}>
            Delete recording
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="error-text" style={{ marginTop: '8px' }}>
          {error}
        </p>
      )}
    </div>
  );
}
