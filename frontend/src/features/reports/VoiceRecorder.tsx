import { useEffect, useRef, useState } from 'react';

export function VoiceRecorder({ onChange }: { onChange: (blob: Blob | undefined) => void }) {
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

  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);

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
        setUrl(URL.createObjectURL(blob));
        setFileName('Recorded audio note');
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

    // Validate audio size (max 15MB)
    if (file.size > 15 * 1024 * 1024) {
      setError('Audio file must be smaller than 15 MB.');
      e.target.value = '';
      return;
    }

    // Validate audio type
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/webm', 'audio/ogg', 'audio/aac'];
    if (!file.type.startsWith('audio/') && !validTypes.includes(file.type)) {
      setError('Please choose a valid audio file (.mp3, .wav, .m4a, .webm, .ogg).');
      e.target.value = '';
      return;
    }

    onChange(file);
    setUrl(URL.createObjectURL(file));
    setFileName(file.name);
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

          <label
            className="secondary-button"
            style={{
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              margin: 0,
            }}
          >
            <span>Choose audio file</span>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg"
              aria-label="Upload audio file"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </label>
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
