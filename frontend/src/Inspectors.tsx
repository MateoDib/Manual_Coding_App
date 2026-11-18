import { isJunction, type JunctionKind } from "./types";
import React, { useEffect, useLayoutEffect, useState, useContext } from "react";
import { Context } from "./editorContext";
import {
  clone,
  type GraphNode,
  type GraphEdge,
  type GraphDoc,
  type EditorArgs,
  type Box,
  type EdgeView,
  ports,
  portLabels,
} from "./types";
import { textHeight } from "./textSizing";
import { dagLabel } from "./sources";
export function NodeInspector({
  node,
  box,
  args,
  doc,
  apply,
  onDirty,
  registerFlush,
}: {
  node: GraphNode;
  box: Box;
  args: EditorArgs;
  doc: GraphDoc;
  apply: (n: GraphNode, b: Box) => void;
  onDirty: (value: boolean) => void;
  registerFlush?: (fn: (() => boolean) | null) => void;
}) {
  const [n, setN] = useState(clone(node)),
    [b, setB] = useState(clone(box)),
    [error, setError] = useState(""),
    [subtopicText, setSubtopicText] = useState(node.subtopics.join("\n")),
    [scopeText, setScopeText] = useState(node.scopes.join("\n"));
  const group = isJunction(n.kind);
  const { undoGraph, redoGraph } = useContext(Context);
  useEffect(() => {
    if (JSON.stringify(node) !== JSON.stringify(n)) {
      setN(clone(node));
      setSubtopicText(node.subtopics.join("\n"));
      setScopeText(node.scopes.join("\n"));
    }
    if (JSON.stringify(box) !== JSON.stringify(b)) setB(clone(box));
  }, [JSON.stringify(node), JSON.stringify(box)]);
  useEffect(() => {
    const timer = setTimeout(() => submit(), 700);
    return () => clearTimeout(timer);
  }, [JSON.stringify(n), JSON.stringify(b)]);

  useEffect(() => {
    onDirty(
      JSON.stringify(n) !== JSON.stringify(node) ||
        JSON.stringify(b) !== JSON.stringify(box),
    );
    return () => onDirty(false);
  }, [n, b, node, box]);
  useLayoutEffect(() => {
    registerFlush?.(() => submit());
    return () => registerFlush?.(null);
  });
  function submit(e?: React.FormEvent): boolean {
    e?.preventDefault();
    if (
      JSON.stringify(n) === JSON.stringify(node) &&
      JSON.stringify(b) === JSON.stringify(box)
    )
      return true;
    if (n.kind === "concept" && n.code === "none") {
      setError("Utilisez l’état « aucun ajout » dans la barre du bas.");
      return false;
    }
    if (n.code && !/^[a-z][a-z0-9_]{0,159}$/.test(n.code)) {
      setError("Utilisez un code en minuscules avec des underscores.");
      return false;
    }
    if (
      !Number.isFinite(b.width) ||
      !Number.isFinite(b.height) ||
      b.width < 18 ||
      b.width > 1200 ||
      b.height < 18 ||
      b.height > 1200
    ) {
      setError("Dimensions comprises entre 18 et 1200.");
      return false;
    }
    setError("");
    apply(n, { ...b, height: Math.max(b.height, textHeight(n, b.width)) });
    return true;
  }
  const targets = [
    ...doc.paths.map((p) => ({
      key: `path:${p.id}`,
      text: dagLabel(doc, p.id),
    })),
    ...doc.nodes
      .filter((v) => v.id !== n.id && v.kind !== "source")
      .map((v) => ({
        key: `node:${v.id}`,
        text: `Concept : ${v.code || v.kind}`,
      })),
    ...doc.edges.map((v) => ({
      key: `edge:${v.id}`,
      text: `Relation : ${doc.nodes.find((n) => n.id === v.source)?.code || v.source} → ${doc.nodes.find((n) => n.id === v.target)?.code || v.target}`,
    })),
  ];
  return (
    <form
      onSubmit={submit}
      onKeyDown={(event) => {
        if (
          !(event.metaKey || event.ctrlKey) ||
          !["z", "y"].includes(event.key.toLowerCase())
        )
          return;
        const dirty =
          JSON.stringify(n) !== JSON.stringify(node) ||
          JSON.stringify(b) !== JSON.stringify(box) ||
          subtopicText !== node.subtopics.join("\n") ||
          scopeText !== node.scopes.join("\n");
        const target = event.target as HTMLElement;
        if (dirty && target.matches('textarea,input:not([type="checkbox"])'))
          return;
        event.preventDefault();
        event.stopPropagation();
        if (dirty && !submit()) return;
        (event.shiftKey || event.key.toLowerCase() === "y"
          ? redoGraph
          : undoGraph)();
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as HTMLElement)) submit();
      }}
    >
      <h3>
        {group
          ? "Jonction"
          : n.kind === "source"
            ? "Source d'information"
            : "Concept"}
      </h3>
      {group && (
        <label>
          Composition
          <select
            aria-label="Type de jonction"
            value={n.kind}
            onChange={(e) =>
              setN({
                ...n,
                kind: e.target.value as JunctionKind,
                dominant:
                  e.target.value === "priority" ? (n.dominant ?? null) : null,
              })
            }
          >
            <option value="coexistence">& Coexistence</option>
            <option value="addition">+ Combinaison additive</option>
            <option value="definition">= Définition / équivalence</option>
            <option value="priority">&gt; / &lt; Priorité</option>
          </select>
        </label>
      )}
      {n.kind === "priority" && (
        <label>
          Élément prioritaire
          <select
            aria-label="Élément prioritaire"
            value={n.dominant || ""}
            onChange={(e) => setN({ ...n, dominant: e.target.value || null })}
          >
            <option value="">Choisir le sujet prioritaire…</option>
            {doc.edges
              .filter((e) => e.kind === "membership" && e.target === n.id)
              .map((e) => doc.nodes.find((v) => v.id === e.source)!)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label || v.code || v.kind}
                </option>
              ))}
          </select>
          <small>
            La priorité suit ce sujet même lorsque les blocs changent de place.
          </small>
        </label>
      )}
      {!group && (
        <>
          <label>
            Code canonique
            <input
              aria-label="Code canonique"
              value={n.code}
              list="canonical-labels"
              maxLength={160}
              pattern={
                n.kind === "concept"
                  ? "(?!none$)[a-z][a-z0-9_]{0,159}"
                  : "[a-z][a-z0-9_]{0,159}"
              }
              title="Code en minuscules avec underscores ; none se choisit dans l’état du codage."
              onChange={(e) =>
                setN({
                  ...n,
                  code: e.target.value.toLowerCase().replace(/\s+/g, "_"),
                })
              }
            />
          </label>
          <datalist id="canonical-labels">
            {(n.kind === "source"
              ? [
                  "newspaper",
                  "television",
                  "social_media",
                  "ipcc_reports",
                  "personal_experience",
                ]
              : args.topics
            ).map((code) => (
              <option key={code} value={code} />
            ))}
          </datalist>
          <label>
            Texte de publication
            <textarea
              aria-label="Texte de publication"
              value={n.label}
              maxLength={2000}
              onChange={(e) => setN({ ...n, label: e.target.value })}
            />
          </label>
          <small>
            Le texte publié et ses retours à la ligne ne modifient pas le code
            d'analyse.
          </small>
          <label>
            Sous-thèmes (un par ligne)
            <textarea
              aria-label="Sous-thèmes"
              value={subtopicText}
              onChange={(e) => {
                setSubtopicText(e.target.value);
                setN({
                  ...n,
                  subtopics: e.target.value
                    .split("\n")
                    .map((v) => v.trim())
                    .filter(Boolean),
                });
              }}
            />
          </label>
          <label>
            Réutiliser un sous-thème
            <select
              aria-label="Réutiliser un sous-thème"
              value=""
              onChange={(e) => {
                const values = [...new Set([...n.subtopics, e.target.value])];
                setN({ ...n, subtopics: values });
                setSubtopicText(values.join("\n"));
              }}
            >
              <option value="">Choisir…</option>
              {[
                ...new Set([
                  ...Object.values(args.subtopics).flat(),
                  ...doc.nodes.flatMap((n) => n.subtopics),
                ]),
              ]
                .sort()
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Portées (une par ligne)
            <textarea
              aria-label="Portées"
              value={scopeText}
              onChange={(e) => {
                setScopeText(e.target.value);
                setN({
                  ...n,
                  scopes: e.target.value
                    .split("\n")
                    .map((v) => v.trim())
                    .filter(Boolean),
                });
              }}
            />
          </label>
          <label>
            Réutiliser une portée
            <select
              aria-label="Ajouter une portée existante"
              value=""
              onChange={(e) => {
                const values = [...new Set([...n.scopes, e.target.value])];
                setN({ ...n, scopes: values });
                setScopeText(values.join("\n"));
              }}
            >
              <option value="">Choisir…</option>
              {[
                ...new Set([
                  ...args.scopes,
                  ...doc.nodes.flatMap((n) => n.scopes),
                  "self",
                  "future_self",
                  "others",
                  "households",
                  "firms",
                ]),
              ]
                .sort()
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
            </select>
          </label>
          {n.kind === "source" && (
            <label>
              DAG, topic ou relation concernée
              <select
                aria-label="Cible de la source"
                value={
                  n.attachment ? `${n.attachment.kind}:${n.attachment.id}` : ""
                }
                onChange={(e) => {
                  const [k, id] = e.target.value.split(":");
                  setN({
                    ...n,
                    attachment: id
                      ? { kind: k as "node" | "edge" | "path", id }
                      : null,
                  });
                }}
              >
                <option value="">Choisir une cible</option>
                {targets.map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.text}
                  </option>
                ))}
              </select>
            </label>
          )}
        </>
      )}
      <div className="two-fields">
        <label>
          Largeur
          <input
            aria-label="Largeur du bloc"
            type="number"
            min={18}
            max={1200}
            value={b.width}
            onChange={(e) => setB({ ...b, width: Number(e.target.value) })}
          />
        </label>
        <label>
          Hauteur
          <input
            aria-label="Hauteur du bloc"
            type="number"
            min={18}
            max={1200}
            value={b.height}
            onChange={(e) => setB({ ...b, height: Number(e.target.value) })}
          />
        </label>
      </div>
      {!group && (
        <button
          type="button"
          onClick={() => {
            setB({ ...b, height: textHeight(n, b.width) });
          }}
        >
          Adapter la hauteur au texte
        </button>
      )}
      <label className="check">
        <input
          type="checkbox"
          checked={b.locked}
          onChange={(e) => setB({ ...b, locked: e.target.checked })}
        />
        Verrouiller la position
      </label>
      {error && <p role="alert">{error}</p>}
      <button className="primary" type="submit">
        Appliquer les modifications
      </button>
    </form>
  );
}
export function EdgeInspector({
  edge,
  view,
  doc,
  apply,
  onDirty,
  registerFlush,
}: {
  edge: GraphEdge;
  view: EdgeView;
  doc: GraphDoc;
  apply: (e: GraphEdge, v: EdgeView) => void;
  onDirty: (value: boolean) => void;
  registerFlush?: (fn: (() => boolean) | null) => void;
}) {
  const { undoGraph, redoGraph } = useContext(Context);
  const [e, setE] = useState(clone(edge)),
    [v, setV] = useState(clone(view)),
    [points, setPoints] = useState(
      view.points.map((p) => `${p.x}, ${p.y}`).join("\n"),
    ),
    [error, setError] = useState("");
  useEffect(() => {
    setE(clone(edge));
    setV(clone(view));
    setPoints(view.points.map((p) => `${p.x}, ${p.y}`).join("\n"));
  }, [JSON.stringify(edge), JSON.stringify(view)]);
  useEffect(() => {
    const timer = setTimeout(() => submit(), 700);
    return () => clearTimeout(timer);
  }, [JSON.stringify(e), JSON.stringify(v), points]);
  useEffect(() => {
    onDirty(
      JSON.stringify(e) !== JSON.stringify(edge) ||
        JSON.stringify(v) !== JSON.stringify(view) ||
        points !== view.points.map((p) => `${p.x}, ${p.y}`).join("\n"),
    );
    return () => onDirty(false);
  }, [e, v, points, edge, view]);
  useLayoutEffect(() => {
    registerFlush?.(() => submit());
    return () => registerFlush?.(null);
  });
  function submit(event?: React.FormEvent): boolean {
    event?.preventDefault();
    if (
      JSON.stringify(e) === JSON.stringify(edge) &&
      JSON.stringify(v) === JSON.stringify(view) &&
      points === view.points.map((p) => `${p.x}, ${p.y}`).join("\n")
    )
      return true;
    const parsed = points.trim()
      ? points
          .trim()
          .split("\n")
          .map((line) => {
            const [x, y] = line.split(",").map(Number);
            return { x, y };
          })
      : [];
    if (
      parsed.some((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y)) ||
      parsed.length > 8 ||
      (v.route === "bezier" && ![0, 2].includes(parsed.length))
    ) {
      setError(
        "Utilisez x, y sur chaque ligne ; une courbe nécessite exactement deux points de contrôle, ou aucun.",
      );
      return false;
    }
    setError("");
    apply(e, { ...v, points: parsed });
    return true;
  }
  return (
    <form
      onSubmit={submit}
      onKeyDown={(event) => {
        if (
          !(event.metaKey || event.ctrlKey) ||
          !["z", "y"].includes(event.key.toLowerCase())
        )
          return;
        const target = event.target as HTMLElement;
        const dirty =
          JSON.stringify(e) !== JSON.stringify(edge) ||
          JSON.stringify(v) !== JSON.stringify(view) ||
          points !== view.points.map((p) => `${p.x}, ${p.y}`).join("\n");
        if (dirty && target.matches('textarea,input:not([type="checkbox"])'))
          return;
        event.preventDefault();
        event.stopPropagation();
        if (dirty && !submit()) return;
        (event.shiftKey || event.key.toLowerCase() === "y"
          ? redoGraph
          : undoGraph)();
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as HTMLElement))
          submit();
      }}
    >
      <h3>
        {e.kind === "membership"
          ? doc.nodes.find((n) => n.id === e.target)?.kind === "coexistence"
            ? "Lien de coexistence (&)"
            : "Opérande de la relation"
          : "Relation"}
      </h3>
      {e.kind === "membership" && (
        <small>
          Ce trait désigne un sujet de la relation ; il n’est pas causal. Les
          unités = et de priorité ont exactement deux sujets. & et + peuvent en
          avoir davantage.
        </small>
      )}
      <label>
        Type
        <select
          value={e.kind}
          onChange={(event) => {
            const kind = event.target.value as GraphEdge["kind"];
            setE({
              ...e,
              kind,
              dominant: kind === "priority" ? e.target : null,
            });
          }}
        >
          <option value="causal">→ Causalité</option>
          <option value="definition">= Définition</option>
          <option value="coexistence">&amp; Coexistence — sans pointe</option>
          <option value="addition">+ Combinaison — sans pointe</option>
          <option value="link">— Trait simple à qualifier</option>
          <option value="priority">Priorité</option>
          {["coexistence", "addition", "definition", "priority"].includes(
            doc.nodes.find((n) => n.id === e.target)!.kind,
          ) && (
            <option value="membership">
              Sujet de la relation — sans causalité
            </option>
          )}
        </select>
      </label>
      <label>
        Style du trait
        <select
          aria-label="Style du trait"
          value={v.stroke || (e.kind === "priority" ? "dashed" : "solid")}
          onChange={(event) =>
            setV({ ...v, stroke: event.target.value as EdgeView["stroke"] })
          }
        >
          <option value="solid">Plein</option>
          <option value="dashed">Tirets</option>
          <option value="dotted">Pointillés</option>
        </select>
      </label>
      <small>
        {e.kind === "causal"
          ? "Une pointe indique la causalité."
          : "Cette relation est représentée sans pointe : elle n’est pas causale."}{" "}
        Cliquez sur le trait pour le sélectionner ; tirez ses extrémités pour le
        reconnecter ou ses poignées rondes pour déplacer son tracé.
      </small>
      {e.kind === "priority" && (
        <label>
          Élément prioritaire
          <select
            value={e.dominant || e.target}
            onChange={(event) => setE({ ...e, dominant: event.target.value })}
          >
            {[e.source, e.target].map((id) => (
              <option key={id} value={id}>
                {doc.nodes.find((n) => n.id === id)?.code || id}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Tracé
        <select
          value={v.route}
          onChange={(e) => {
            setV({ ...v, route: e.target.value as EdgeView["route"] });
            setPoints("");
          }}
        >
          <option value="straight">Droit</option>
          <option value="orthogonal">Orthogonal</option>
          <option value="bezier">Courbe</option>
        </select>
      </label>
      {(["source_port", "target_port"] as const).map((key) => (
        <label key={key}>
          {key === "source_port" ? "Ancrage de départ" : "Ancrage d'arrivée"}
          <select
            value={v[key]}
            onChange={(e) => setV({ ...v, [key]: e.target.value })}
          >
            {ports.map((p) => (
              <option key={p} value={p}>
                {portLabels[p]}
              </option>
            ))}
          </select>
        </label>
      ))}
      {v.route !== "straight" && (
        <label>
          {v.route === "bezier" ? "Points de contrôle" : "Points de passage"}
          <textarea
            value={points}
            onChange={(e) => setPoints(e.target.value)}
            placeholder="x, y (une ligne par point ; vide = automatique)"
          />
        </label>
      )}
      {["definition", "priority", "coexistence", "addition"].includes(
        e.kind,
      ) && (
        <>
          <label>
            Position du symbole
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={v.label_t}
              onChange={(e) => setV({ ...v, label_t: Number(e.target.value) })}
            />
          </label>
          <button
            type="button"
            onClick={() =>
              setV({ ...v, label_t: 0.5, label_dx: 0, label_dy: 0 })
            }
          >
            Centrer le symbole sur le trait
          </button>
          <small>
            Le symbole peut aussi être déplacé directement à la souris.
          </small>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      <button type="submit" className="primary">
        Appliquer la relation
      </button>
    </form>
  );
}
