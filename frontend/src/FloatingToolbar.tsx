import React, {
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { useViewport } from "@xyflow/react";
import type { Box } from "./types";

export function FloatingToolbar({
  box,
  canvas,
  children,
  hidden = false,
  compact = false,
}: {
  box: Box;
  canvas: RefObject<HTMLDivElement>;
  children: React.ReactNode;
  hidden?: boolean;
  compact?: boolean;
}) {
  const viewport = useViewport(),
    ref = useRef<HTMLDivElement>(null),
    [size, setSize] = useState({
      width: 250,
      height: 44,
      canvas: 800,
      canvasHeight: 600,
    });
  useLayoutEffect(() => {
    const measure = () => {
      if (ref.current?.offsetWidth)
        setSize({
          width: ref.current.offsetWidth,
          height: ref.current.offsetHeight,
          canvas: canvas.current?.clientWidth || 800,
          canvasHeight: canvas.current?.clientHeight || 600,
        });
    };
    const observer = new ResizeObserver(measure);
    if (ref.current) observer.observe(ref.current);
    if (canvas.current) observer.observe(canvas.current);
    measure();
    return () => observer.disconnect();
  }, []);
  const center = (box.x + box.width / 2) * viewport.zoom + viewport.x;
  let left = Math.max(
    size.width / 2 + 14,
    Math.min(size.canvas - size.width / 2 - 14, center),
  );
  const above = box.y * viewport.zoom + viewport.y - size.height - 12,
    below = (box.y + box.height) * viewport.zoom + viewport.y + 12;
  let top =
    above >= 14
      ? above
      : below + size.height < size.canvasHeight - 14
        ? below
        : Math.max(14, Math.min(size.canvasHeight - size.height - 14, above));
  if (above < 14 && below + size.height >= size.canvasHeight - 14) {
    const before = box.x * viewport.zoom + viewport.x - size.width - 12,
      after = (box.x + box.width) * viewport.zoom + viewport.x + 12;
    if (before >= 14 || after + size.width <= size.canvas - 14) {
      left = (before >= 14 ? before : after) + size.width / 2;
      top = Math.max(
        14,
        Math.min(
          size.canvasHeight - size.height - 14,
          (box.y + box.height / 2) * viewport.zoom +
            viewport.y -
            size.height / 2,
        ),
      );
    }
  }
  return (
    <div
      ref={ref}
      className={`selection-tools nodrag nopan${compact ? " edge-tools" : ""}`}
      role="group"
      aria-label={compact ? "Actions du lien" : "Actions de la sélection"}
      hidden={hidden}
      style={{ left, top, transform: "translateX(-50%)" }}
      onPointerDown={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  );
}
