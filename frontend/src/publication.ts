import { same } from "./editorState";
import type { EditorArgs, GraphDoc } from "./types";

export type ExportKind = "tikz" | "tex" | "pdf" | "json";
export function publicationReady(
  doc: GraphDoc,
  args: EditorArgs,
  saving: boolean,
  dirty: boolean,
) {
  return (
    !saving &&
    !dirty &&
    !args.error &&
    !!args.latex?.digest &&
    args.latex.revision === args.revision &&
    args.latex.document_key === args.document_key &&
    same(doc, args.document)
  );
}
