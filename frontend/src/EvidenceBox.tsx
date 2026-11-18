import React from "react";
import type { ObjectRecord } from "./types";

export function quoteMatches(response: string, text: string) {
  const matches: { start: number; end: number; text: string }[] = [];
  if (!text) return matches;
  const raw = [...response],
    normalized: string[] = [],
    starts: number[] = [],
    ends: number[] = [];
  for (let i = 0; i < raw.length; i++) {
    const start = i;
    let char = raw[i];
    if (char === "\r") {
      char = "\n";
      if (raw[i + 1] === "\n") i++;
    }
    normalized.push(char);
    starts.push(start);
    ends.push(i + 1);
  }
  const haystack = normalized.join(""),
    needle = text.replace(/\r\n?/g, "\n"),
    length = [...needle].length;
  let at = 0;
  while (at <= haystack.length && matches.length < 200) {
    const found = haystack.indexOf(needle, at);
    if (found < 0) break;
    const position = [...haystack.slice(0, found)].length;
    const start = starts[position],
      end = ends[position + length - 1];
    matches.push({ start, end, text: raw.slice(start, end).join("") });
    at = found + 1;
  }
  return matches;
}
export function EvidenceBox({
  response,
  meta,
  onChange,
}: {
  response: string;
  meta: ObjectRecord;
  onChange: (value: ObjectRecord) => void;
}) {
  if (!meta) return null;
  const matches = quoteMatches(response, meta.quote.text);
  const valid = matches.some(
    (m) => m.start === meta.quote.start && m.end === meta.quote.end,
  );
  function setText(text: string) {
    const found = quoteMatches(response, text),
      position = found.length === 1 ? found[0] : null;
    onChange({
      ...meta,
      review: position ? "expressed" : "unreviewed",
      quote: {
        text: position?.text ?? text,
        start: position?.start ?? null,
        end: position?.end ?? null,
      },
    });
  }
  return (
    <div className="evidence-box" onKeyDown={(e) => e.stopPropagation()}>
      <label>
        Citation du participant
        <textarea
          aria-label="Citation du participant"
          placeholder="Coller le passage exact de cette réponse…"
          maxLength={5000}
          value={meta.quote.text}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      {meta.quote.text && (
        <small role="status">
          {valid
            ? "✓ Citation retrouvée dans la réponse actuelle."
            : matches.length > 1
              ? "Ce passage apparaît plusieurs fois : choisissez sa position."
              : "Ce texte ne figure pas exactement dans la réponse actuelle."}
        </small>
      )}
      {matches.length > 1 && (
        <select
          aria-label="Occurrence de la citation"
          value={valid ? String(meta.quote.start) : ""}
          onChange={(e) => {
            const position = matches.find(
              (m) => m.start === Number(e.target.value),
            );
            if (position)
              onChange({
                ...meta,
                review: "expressed",
                quote: { ...meta.quote, ...position },
              });
          }}
        >
          <option value="">Choisir le passage…</option>
          {matches.map((m, i) => (
            <option key={m.start} value={m.start}>
              Passage {i + 1} · caractère {m.start + 1}
            </option>
          ))}
        </select>
      )}
      <select
        aria-label="Sens de la citation"
        value={meta.review}
        onChange={(e) =>
          onChange({
            ...meta,
            review: e.target.value as ObjectRecord["review"],
          })
        }
      >
        <option value="unreviewed">Attribution à vérifier</option>
        <option value="expressed" disabled={!valid}>
          Ce passage exprime cet élément
        </option>
        <option value="not_discussed">Non évoqué dans cette réponse</option>
        <option value="withdrawn" disabled={!valid}>
          Ce passage remet cet élément en cause
        </option>
      </select>
      <small>
        Le contrôle vérifie le texte ; vous restez responsable de son
        interprétation.
      </small>
    </div>
  );
}
