import type { GraphNode, GraphDoc, Port, Point } from "./types";
import { anchor } from "./geometry";
import { ports } from "./types";

export const symbols = [
  [
    "—",
    "Trait sans pointe, à qualifier ensuite avec une relation du coding scheme.",
  ],
  [
    "→",
    "Lien causal ou conséquent positif. La direction du changement figure dans le nom du topic.",
  ],
  ["=", "Définition ou équivalence dans le raisonnement du participant."],
  [
    "&",
    "Coexistence sans causalité. Sélectionnez au moins deux sujets pour créer une unité ciblable par des flèches.",
  ],
  [
    "+",
    "Combinaison additive sans causalité. Sélectionnez au moins deux sujets pour créer une unité ciblable par des flèches.",
  ],
  ["<", "L’élément à l’arrivée prend le pas sur celui au départ."],
  [">", "L’élément au départ prend le pas sur celui à l’arrivée."],
  ["()", "Sous-thèmes agrégés au topic sélectionné, jamais des blocs séparés."],
  ["[]", "Acteur ou portée du topic sélectionné, jamais un bloc séparé."],
  [
    "|",
    "Source d’information du DAG actif ; sélectionnez un topic ou une relation pour un rattachement précis. Écrivez | newspaper sur la toile ou cliquez ici et saisissez la source. Réglages permet de changer la cible.",
  ],
  [
    ";",
    "Autre DAG : ajoute un bloc indépendant. Les blocs non reliés forment automatiquement des DAGs différents, sans séparateur obligatoire.",
  ],
  [
    "none",
    "Aucun ajout substantiel dans cette réponse. État du codage, sans créer de topic.",
  ],
] as const;

export function canonical(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^[^a-z]+/, "")
    .slice(0, 160);
}
export type ParsedEntry =
  | { type: "symbol"; value: string }
  | { type: "qualifier"; subtopics: string[]; scopes: string[] }
  | {
      type: "node";
      kind: GraphNode["kind"];
      code: string;
      label: string;
      subtopics: string[];
      scopes: string[];
    };

// Balanced delimiters are parsed at their own depth: commas inside company(sme,
// agriculture) remain part of that scope. No eval, HTML or TeX interpretation.
function splitList(text: string): string[] {
  const out: string[] = [];
  let start = 0,
    depth = 0;
  for (let i = 0; i < text.length; i++) {
    if ("([".includes(text[i])) depth++;
    if (")]".includes(text[i])) depth--;
    if (text[i] === "," && depth === 0) {
      out.push(text.slice(start, i).trim());
      start = i + 1;
    }
  }
  out.push(text.slice(start).trim());
  return out.filter(Boolean);
}
export function parseEntry(raw: string): ParsedEntry {
  const text = raw.trim();
  const symbol = text === "-->" || text === "->" ? "→" : text;
  if (symbols.some(([s]) => s === symbol))
    return { type: "symbol", value: symbol };
  const source = text.startsWith("|");
  const value = source ? text.slice(1).trim() : text;
  let base = "",
    i = 0;
  while (i < value.length && !"([".includes(value[i])) base += value[i++];
  if (/[\])]/.test(base))
    throw new Error("Parenthèse ou crochet sans ouverture.");
  const subtopics: string[] = [],
    scopes: string[] = [];
  while (i < value.length) {
    if (/\s/.test(value[i])) {
      i++;
      continue;
    }
    const open = value[i],
      close = open === "(" ? ")" : "]";
    if (!"([".includes(open))
      throw new Error(
        "Placez les précisions après le topic : topic(sous-thème)[portée].",
      );
    const stack = [close];
    let start = ++i;
    while (i < value.length && stack.length) {
      const c = value[i];
      if (c === "(") stack.push(")");
      else if (c === "[") stack.push("]");
      else if (c === ")" || c === "]") {
        if (stack.pop() !== c)
          throw new Error("Parenthèses et crochets mal imbriqués.");
      }
      if (stack.length) i++;
    }
    if (stack.length)
      throw new Error("Fermez la parenthèse ou le crochet pour terminer.");
    (open === "(" ? subtopics : scopes).push(
      ...splitList(value.slice(start, i)),
    );
    i++;
  }
  base = base.trim();
  if (!base && !source && (subtopics.length || scopes.length))
    return { type: "qualifier", subtopics, scopes };
  if (/[&+<>=;{}|]/.test(base) || base.includes("-->") || base.includes("→"))
    throw new Error(
      "Saisissez un seul topic ou symbole à la fois. Les accolades ne sont pas définies par le coding scheme.",
    );
  if (!base) throw new Error("Saisissez un topic ou un symbole du schéma.");
  const code = canonical(base);
  if (!code) throw new Error("Le topic doit contenir au moins une lettre.");
  if (code === "none")
    throw new Error("none est un état de codage, sans précision ni bloc.");
  if (
    subtopics.length > 50 ||
    scopes.length > 50 ||
    [...subtopics, ...scopes].some((v) => v.length > 500)
  )
    throw new Error("Trop de précisions ou précision trop longue.");
  return {
    type: "node",
    kind: source ? "source" : "concept",
    code,
    label: base.replaceAll("_", " "),
    subtopics,
    scopes,
  };
}
export function nodeText(n: GraphNode): string {
  if (n.kind === "addition") return "+";
  if (n.kind === "coexistence") return "&";
  if (n.kind === "definition") return "=";
  if (n.kind === "priority") return ">";
  return (
    (n.kind === "source" ? "| " : "") +
    (n.label || n.code.replaceAll("_", " ")) +
    (n.subtopics.length ? ` (${n.subtopics.join(", ")})` : "") +
    (n.scopes.length ? `[${n.scopes.join(", ")}]` : "")
  );
}
export function nearestPort(doc: GraphDoc, id: string, p: Point): Port {
  const b = doc.layout.nodes[id];
  return ports.reduce((best, v) => {
    const a = anchor(b, v),
      prev = anchor(b, best);
    return Math.hypot(a.x - p.x, a.y - p.y) <
      Math.hypot(prev.x - p.x, prev.y - p.y)
      ? v
      : best;
  }, "left" as Port);
}
export const opposite: Record<Port, Port> = {
  left: "right",
  right: "left",
  top: "bottom",
  bottom: "top",
  "top-left": "bottom-right",
  "top-right": "bottom-left",
  "bottom-left": "top-right",
  "bottom-right": "top-left",
};
