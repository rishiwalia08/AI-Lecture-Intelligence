function toClock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function TimestampLinks({ refs = [] }) {
  if (!refs.length) return null;
  return (
    <div>
      {refs.map((r, idx) => (
        <div key={`${r.chunk_id || idx}-${r.start_time || 0}`} style={{ marginBottom: 8 }}>
          <strong>{toClock(r.start_time)} - {toClock(r.end_time)}</strong>
          {r.youtube_link ? (
            <>
              {" "}
              <a href={r.youtube_link} target="_blank" rel="noreferrer">Jump</a>
            </>
          ) : null}
          <div className="muted" style={{ fontSize: 13 }}>{r.text}</div>
        </div>
      ))}
    </div>
  );
}
