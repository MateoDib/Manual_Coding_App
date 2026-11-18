import { createContext } from "react";
import type { GraphDoc, Box } from "./types";
import type { Vocabulary } from "./suggestions";
export type EditorContext = {
  doc: GraphDoc;
  readOnly: boolean;
  beginGesture: () => void;
  resize: (id: string, b: Partial<Box>, finish: boolean) => void;
  moveLabel: (id: string, dx: number, dy: number, finish: boolean) => void;
  editing: string | null;
  editText: (id: string, text: string, finish: boolean) => boolean;
  stopEditing: () => void;
  initialText: (id: string) => string | undefined;
  undoGraph: () => void;
  redoGraph: () => void;
  vocabulary: Vocabulary;
  selectEdge: (id: string) => void;
  moveRoutePoint: (
    id: string,
    index: number,
    point: { x: number; y: number },
    finish: boolean,
  ) => void;
};
export const Context = createContext<EditorContext>(null!);
