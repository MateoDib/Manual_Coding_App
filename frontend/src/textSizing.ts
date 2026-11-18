import type { GraphNode } from "./types";

/** Browser text metrics are an editing aid; the compiled PDF is authoritative. */
export function textHeight(node: GraphNode, width: number): number {
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return 64;
  function lines(text: string, size: number): number {
    context!.font = `${size}px "Times New Roman",serif`;
    const available = Math.max(20, width - 18);
    return text.split("\n").reduce((sum, line) => {
      let count = 1,
        current = "";
      for (const word of line.split(/\s+/)) {
        const joined = current ? current + " " + word : word;
        if (context!.measureText(joined).width > available) {
          if (current) count++;
          count += Math.max(
            0,
            Math.ceil(context!.measureText(word).width / available) - 1,
          );
          current = word;
        } else current = joined;
      }
      return sum + count;
    }, 0);
  }
  return Math.min(
    1200,
    Math.max(
      48,
      20 +
        17 * lines(node.label || node.code.replaceAll("_", " "), 14) +
        (node.subtopics.length
          ? 14 *
              lines(
                "(" + node.subtopics.join(", ").replaceAll("_", " ") + ")",
                11,
              ) +
            2
          : 0) +
        (node.scopes.length
          ? 14 *
              lines(
                "[" + node.scopes.join(", ").replaceAll("_", " ") + "]",
                11,
              ) +
            2
          : 0),
    ),
  );
}
