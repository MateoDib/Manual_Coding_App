import React, { useEffect, useRef, useState } from "react";
import type { GraphDoc, PreviousSource } from "./types";
import { DagThumbnail } from "./DagThumbnail";

type Selection = Record<string, { revision: number; path_ids: string[] }>;
const statusName: Record<string, string> = {
  draft: "Brouillon",
  coded: "Codé",
  none: "none · aucun ajout",
  missing: "Non codé",
};
export function DagPicker({
  sources,
  doc,
  busy,
  error,
  close,
  submit,
}: {
  sources: PreviousSource[];
  doc: GraphDoc;
  busy: boolean;
  error: string | null;
  close: () => void;
  submit: (extra: Record<string, unknown>) => void;
}) {
  const [selected, setSelected] = useState<Selection>({}),
    [query, setQuery] = useState(""),
    [mode, setMode] = useState("replace"),
    [notice, setNotice] = useState("");
  const dialog = useRef<HTMLElement>(null),
    search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const returnTo = document.activeElement as HTMLElement | null;
    const timer = requestAnimationFrame(() =>
      search.current?.focus({ preventScroll: true }),
    );
    return () => {
      cancelAnimationFrame(timer);
      if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    const safe: Selection = {};
    let changed = false;
    for (const [key, item] of Object.entries(selected)) {
      const source = sources.find((s) => s.key === key);
      if (
        source &&
        source.revision === item.revision &&
        item.path_ids.every((id) => source.paths.some((p) => p.id === id))
      )
        safe[key] = item;
      else changed = true;
    }
    if (changed) {
      setSelected(safe);
      setNotice(
        "Une figure d’origine a été actualisée. Vérifiez sa miniature et sélectionnez-la à nouveau.",
      );
    }
  }, [sources, selected]);
  function choose(source: PreviousSource, ids: string[]) {
    setNotice("");
    setSelected((old) => {
      const next = { ...old };
      if (ids.length)
        next[source.key] = { revision: source.revision, path_ids: ids };
      else delete next[source.key];
      return next;
    });
  }
  const firstPreviewKey =
    [...sources].reverse().find((source) => source.paths.length)?.key ||
    sources.at(-1)?.key;
  const selectedPaths = sources.flatMap((s) =>
    s.paths.filter((p) => selected[s.key]?.path_ids.includes(p.id)),
  );
  const count = selectedPaths.length;
  const nodes = selectedPaths.reduce(
    (sum, p) => sum + p.preview.nodes.length,
    mode === "append" ? doc.nodes.length : 0,
  );
  const edges = selectedPaths.reduce(
    (sum, p) => sum + p.preview.edges.length,
    mode === "append" ? doc.edges.length : 0,
  );
  const tooLarge = mode !== "origin" && (nodes > 150 || edges > 500);
  const needle = query.trim().toLocaleLowerCase();
  const filtered = [...sources]
    .reverse()
    .filter(
      (s) =>
        !needle ||
        [
          String(s.order),
          s.question,
          s.response,
          ...s.paths.flatMap((p) => p.topics),
        ].some((text) => text.toLocaleLowerCase().includes(needle)),
    );
  return (
    <div
      className="dag-picker-backdrop"
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        ref={dialog}
        className="dag-picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dag-picker-title"
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s")
            e.preventDefault();
          if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            close();
          }
          if (e.key === "Tab") {
            const controls = [
              ...(dialog.current?.querySelectorAll<HTMLElement>(
                'button:not([disabled]),input:not([disabled]),select:not([disabled]),summary,[tabindex="0"]',
              ) || []),
            ].filter((el) => el.getClientRects().length);
            const first = controls[0],
              last = controls.at(-1);
            if (!first) return;
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus({ preventScroll: true });
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first.focus({ preventScroll: true });
            }
          }
        }}
      >
        <div className="panel-heading">
          <div>
            <h3 id="dag-picker-title">Reprendre un autre DAG</h3>
            <small>
              Questions précédentes du même entretien · codages de ce codeur
            </small>
          </div>
          <button aria-label="Fermer le choix des DAGs" onClick={close}>
            ×
          </button>
        </div>
        <label className="dag-search">
          Rechercher une paire ou un topic
          <input
            ref={search}
            type="search"
            aria-label="Rechercher dans les paires précédentes"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Question, réponse, topic…"
          />
        </label>
        {notice && (
          <p className="dag-picker-notice" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="dag-picker-notice" role="alert">
            {error}
          </p>
        )}
        <div className="dag-pair-list">
          {filtered.map((source) => (
            <Pair
              key={source.key}
              source={source}
              initiallyOpen={source.key === firstPreviewKey}
              selected={selected[source.key]?.path_ids || []}
              choose={(ids) => choose(source, ids)}
              disabled={busy}
            />
          ))}
          {!filtered.length && (
            <p>
              {sources.length
                ? "Aucune paire ne correspond à cette recherche."
                : "Aucune question précédente dans cet entretien."}
            </p>
          )}
        </div>
        <footer className="dag-picker-footer">
          <div className="dag-selection-summary">
            <strong>
              {count} DAG{count > 1 ? "s" : ""} sélectionné
              {count > 1 ? "s" : ""}
            </strong>
            <button disabled={!count || busy} onClick={() => setSelected({})}>
              Effacer la sélection
            </button>
          </div>
          <label>
            Utilisation
            <select
              aria-label="Mode de reprise"
              value={mode}
              disabled={busy}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="replace">
                Remplacer la figure actuelle par ces copies
              </option>
              <option value="append">
                Ajouter ces copies à la figure actuelle
              </option>
              <option value="origin">
                Renseigner l’origine sans modifier la figure
              </option>
            </select>
          </label>
          <small>
            Les paires d’origine sont conservées. Vous pourrez modifier les
            copies et annuler cette reprise avec ⌘/Ctrl Z.
          </small>
          {tooLarge && (
            <p role="alert">
              La sélection dépasserait la limite de 150 objets ou 500 liens.
              Choisissez moins de DAGs.
            </p>
          )}
          <div className="dag-picker-actions">
            <button onClick={close}>Annuler</button>
            <button
              className="primary"
              disabled={!count || busy || tooLarge}
              onClick={() =>
                submit({
                  selections: sources
                    .filter((s) => selected[s.key])
                    .map((s) => ({
                      source_key: s.key,
                      revision: selected[s.key].revision,
                      path_ids: selected[s.key].path_ids,
                    })),
                  append: mode === "append",
                  origin_only: mode === "origin",
                })
              }
            >
              {busy
                ? "Reprise en cours…"
                : `Reprendre ${count > 1 ? "les " + count + " DAGs sélectionnés" : "le DAG sélectionné"}`}
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
function Pair({
  source,
  initiallyOpen,
  selected,
  choose,
  disabled,
}: {
  source: PreviousSource;
  initiallyOpen: boolean;
  selected: string[];
  choose: (ids: string[]) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const root = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      const item = root.current,
        list = item?.closest<HTMLElement>(".dag-pair-list");
      if (item && list)
        list.scrollTop +=
          item.getBoundingClientRect().top - list.getBoundingClientRect().top;
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);
  return (
    <details
      ref={root}
      className="dag-pair"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        <span className="dag-pair-heading">
          <strong>Paire {source.order}</strong>
          <span className="dag-question-excerpt">
            {source.question || "Question sans texte"}
          </span>
          <small>
            {source.paths.length} DAG{source.paths.length > 1 ? "s" : ""} ·{" "}
            {source.status === "none" && source.paths.length
              ? "none · figure de référence"
              : statusName[source.status] || source.status}
            {!!selected.length && ` · ${selected.length} sélectionné(s)`}
          </small>
        </span>
      </summary>
      {open && (
        <div className="dag-pair-content">
          <div className="dag-pair-transcript">
            <section>
              <h4>Question</h4>
              <div tabIndex={0}>{source.question}</div>
            </section>
            <section>
              <h4>Réponse</h4>
              <div tabIndex={0}>{source.response}</div>
            </section>
          </div>
          {!!source.paths.length && (
            <button
              className="dag-select-pair"
              disabled={disabled}
              onClick={() =>
                choose(
                  selected.length === source.paths.length
                    ? []
                    : source.paths.map((p) => p.id),
                )
              }
            >
              {selected.length === source.paths.length
                ? "Désélectionner cette paire"
                : "Choisir tous les DAGs de cette paire"}
            </button>
          )}
          <div className="dag-cards">
            {source.paths.map((p) => (
              <label
                className={
                  "dag-card" + (selected.includes(p.id) ? " is-selected" : "")
                }
                key={p.id}
              >
                <span className="dag-card-title">
                  <input
                    aria-label={`Choisir ${p.label} de la paire ${source.order}`}
                    type="checkbox"
                    disabled={disabled}
                    checked={selected.includes(p.id)}
                    onChange={(e) =>
                      choose(
                        e.target.checked
                          ? [...selected, p.id]
                          : selected.filter((id) => id !== p.id),
                      )
                    }
                  />
                  <strong>{p.label}</strong>
                </span>
                <DagThumbnail
                  doc={p.preview}
                  label={`${p.label} · paire ${source.order}`}
                />
                <span className="dag-topics" title={p.topics.join(", ")}>
                  {p.topics.join(", ")}
                </span>
              </label>
            ))}
          </div>
          {!source.paths.length && (
            <p>
              Aucun DAG réutilisable n’a encore été enregistré pour cette paire.
            </p>
          )}
        </div>
      )}
    </details>
  );
}
