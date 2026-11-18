import { canonical, symbols } from "./entry";
export type Vocabulary = {
  topics: string[];
  subtopics: Record<string, string[]>;
  scopes: string[];
  labels?: Record<string, string[]>;
};
export type EntryContext = {
  kind: "topics" | "subtopics" | "scopes";
  start: number;
  end: number;
  query: string;
  topic: string;
};
export type Suggestion = { value: string; label: string; preferred: boolean };
const fold = (text: string) =>
  text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();

export function entryContext(
  text: string,
  cursor: number,
  code: string,
): EntryContext | null {
  const pos = Math.max(0, Math.min(cursor, text.length));
  const stack: { open: string; at: number }[] = [];
  for (let i = 0; i < pos; i++) {
    const c = text[i];
    if (c === "(" || c === "[") stack.push({ open: c, at: i });
    else if (c === ")" || c === "]") {
      if (!stack.length || stack.at(-1)!.open !== (c === ")" ? "(" : "["))
        return null;
      stack.pop();
    }
  }
  const first = text.search(/[([]/),
    topic = code || canonical(first < 0 ? text : text.slice(0, first));
  if (!stack.length) {
    if (first >= 0 && pos > first) return null;
    const end = first >= 0 ? first : text.length;
    if (symbols.some(([s]) => s === text.trim()) || text.trim().startsWith("|"))
      return null;
    return {
      kind: "topics",
      start: 0,
      end,
      query: text.slice(0, pos).trim(),
      topic,
    };
  }
  // Nested parentheses inside a scope belong to that scope, not to subtopics.
  const outer = stack[0],
    kind = outer.open === "[" ? "scopes" : "subtopics";
  let start = outer.at + 1,
    depth = 1;
  for (let i = start; i < pos; i++) {
    if (text[i] === "(" || text[i] === "[") depth++;
    else if (text[i] === ")" || text[i] === "]") depth--;
    else if (text[i] === "," && depth === 1) start = i + 1;
  }
  while (start < pos && /\s/.test(text[start])) start++;
  let end = pos;
  for (let i = pos; i < text.length; i++) {
    if (
      (text[i] === "," && depth === 1) ||
      ((text[i] === ")" || text[i] === "]") && depth === 1)
    ) {
      end = i;
      break;
    }
    if (text[i] === "(" || text[i] === "[") depth++;
    else if (text[i] === ")" || text[i] === "]") depth--;
    end = i + 1;
  }
  return {
    kind,
    start,
    end,
    query: text.slice(start, pos).trim(),
    topic,
  };
}
export function suggest(
  context: EntryContext | null,
  vocabulary: Vocabulary,
  limit = 8,
): Suggestion[] {
  if (!context || (!context.query && context.kind === "topics")) return [];
  const q = fold(context.query),
    local = new Set(vocabulary.subtopics[context.topic] || []);
  const values =
    context.kind === "topics"
      ? vocabulary.topics
      : context.kind === "scopes"
        ? vocabulary.scopes
        : Object.values(vocabulary.subtopics).flat();
  const score = (value: string) => {
    const aliases = [
      value,
      ...(context.kind === "topics" ? vocabulary.labels?.[value] || [] : []),
    ].map(fold);
    const rank = Math.min(
      ...aliases.map((s) =>
        s === q
          ? 0
          : s.startsWith(q)
            ? 1
            : s.split(" ").some((w) => w.startsWith(q))
              ? 2
              : s.includes(q)
                ? 3
                : 100,
      ),
    );
    return (
      rank * 10 + (context.kind === "subtopics" && !local.has(value) ? 1 : 0)
    );
  };
  return [...new Set(values)]
    .filter((v) => v !== "none" && score(v) < 1000)
    .sort((a, b) => score(a) - score(b) || a.localeCompare(b))
    .slice(0, limit)
    .map((value) => ({
      value,
      label: value.replaceAll("_", " "),
      preferred: context.kind === "subtopics" && local.has(value),
    }));
}
export function completeEntry(
  text: string,
  context: EntryContext,
  value: string,
): { text: string; cursor: number } {
  const before = text.slice(0, context.start),
    after = text.slice(context.end);
  const completed = before + value + after,
    stack: string[] = [];
  for (const c of completed) {
    if (c === "(" || c === "[") stack.push(c);
    else if (c === ")" || c === "]") stack.pop();
  }
  return {
    text:
      completed +
      stack
        .reverse()
        .map((c) => (c === "(" ? ")" : "]"))
        .join(""),
    cursor: before.length + value.length,
  };
}
