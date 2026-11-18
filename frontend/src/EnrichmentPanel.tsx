import React from "react";
import type { EditorArgs, GraphDoc } from "./types";
const names: Record<string, string> = {
  topic: "Topics",
  subtopic: "Sous-thèmes",
  scope: "Portées",
  source: "Sources",
  group: "Unités de relation",
  relation: "Relations",
};
export function EnrichmentPanel({
  args,
  doc,
  busy,
  pending,
  close,
  mutate,
  command,
}: {
  args: EditorArgs;
  doc: GraphDoc;
  busy: boolean;
  pending: boolean;
  close: () => void;
  mutate: (fn: (d: GraphDoc) => void) => void;
  command: (action: string, extra?: Record<string, unknown>) => void;
}) {
  const m = args.enrichment;
  const resumed =
    m?.dags.filter((d) => ["continued", "mixed"].includes(d.origin)).length ||
    0;
  const created = m?.dags.filter((d) => d.origin === "new").length || 0;
  return (
    <section
      className="options-panel enrichment-panel"
      aria-label="Enrichissement du DAG"
    >
      <div className="panel-heading">
        <h3>Enrichissement</h3>
        <button aria-label="Fermer l’enrichissement" onClick={close}>
          ×
        </button>
      </div>
      <p>
        {m?.dag_count || 0} DAG(s)
        {resumed ? ` · ${resumed} repris ou complété(s)` : ""}
        {created ? ` · ${created} créé(s) ici` : ""}
      </p>
      {pending && (
        <small role="status">
          Sauvegarde en cours ; les chiffres décrivent la dernière version
          enregistrée.
        </small>
      )}
      {!m?.history_complete && (
        <p>
          Une paire précédente reste à coder ou à vérifier. La nouveauté est
          provisoire.
        </p>
      )}
      {!!m?.issues.length && (
        <details>
          <summary>Points à vérifier</summary>
          {m.issues.map((v, i) => (
            <p key={i}>{v}</p>
          ))}
        </details>
      )}
      <div className="metrics-table">
        <table>
          <thead>
            <tr>
              <th>Éléments</th>
              <th>Uniques</th>
              <th>Occurrences</th>
              <th>Nouveaux</th>
              <th>Cités ici</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(names).map(([k, label]) => (
              <tr key={k}>
                <th>{label}</th>
                <td>{m?.counts[k]?.total || 0}</td>
                <td>{m?.counts[k]?.occurrences || 0}</td>
                <td>{m?.counts[k]?.new || 0}</td>
                <td>{m?.counts[k]?.expressed || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small>
        « Nouveau » compare tout le codage antérieur de cet entretien. Une copie
        ou un redessin ne compte pas comme une nouvelle mention sans citation de
        cette réponse.
      </small>
      {!!m?.removed.length && (
        <details>
          <summary>Éléments retirés d’une reprise ({m.removed.length})</summary>
          {m.removed.map((v) => (
            <label key={v.removal_key}>
              {v.label}
              <select
                aria-label={"Motif de retrait : " + v.label}
                value={doc.tracking?.removals[v.removal_key] || ""}
                disabled={busy}
                onChange={(e) =>
                  mutate((d) => {
                    if (e.target.value)
                      d.tracking!.removals[v.removal_key] = e.target.value as
                        "withdrawn" | "correction" | "not_relevant";
                    else delete d.tracking!.removals[v.removal_key];
                  })
                }
              >
                <option value="">À préciser…</option>
                <option value="withdrawn">
                  Retrait explicite par le participant
                </option>
                <option value="correction">Correction du codage</option>
                <option value="not_relevant">
                  Hors du raisonnement actuel
                </option>
              </select>
            </label>
          ))}
        </details>
      )}
      <details>
        <summary>Figure indépendante</summary>
        <button
          disabled={busy}
          onClick={() =>
            mutate((d) => {
              d.tracking!.parents = [];
              d.tracking!.dag_links = Object.fromEntries(
                d.paths.map((p) => [p.id, []]),
              );
              d.tracking!.removals = {};
              for (const meta of Object.values(d.tracking!.objects)) {
                meta.origin = "created";
                meta.source = null;
              }
            })
          }
        >
          Confirmer une figure indépendante
        </button>
        <button
          disabled={busy}
          onClick={() => {
            command("new_graph");
            close();
          }}
        >
          Commencer une figure vide
        </button>
      </details>
    </section>
  );
}
