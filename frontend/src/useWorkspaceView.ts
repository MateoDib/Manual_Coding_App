import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  useNodesInitialized,
  useReactFlow,
  type Viewport,
} from "@xyflow/react";
import { centeredView, readView, saveView } from "./editorState";

export function useWorkspaceView(
  key: string,
  canvas: RefObject<HTMLDivElement>,
  count: number,
  review: boolean,
) {
  const rf = useReactFlow(),
    controller = useRef(rf),
    initialized = useNodesInitialized(),
    cached = useRef(readView(key)),
    ready = useRef(false),
    size = useRef({ width: 0, height: 0 });
  controller.current = rf;
  const [height, setHeight] = useState(review ? 460 : 680);
  useLayoutEffect(() => {
    let host: Window = window;
    try {
      if (window.parent.innerHeight) host = window.parent;
    } catch {}
    const measure = () => {
      let available = host.innerHeight;
      try {
        available -= window.frameElement?.getBoundingClientRect().top ?? 0;
      } catch {}
      setHeight(
        review
          ? Math.max(260, Math.min(500, available - 200))
          : Math.max(360, available - 14),
      );
    };
    measure();
    host.addEventListener("resize", measure);
    host.visualViewport?.addEventListener("resize", measure);
    return () => {
      host.removeEventListener("resize", measure);
      host.visualViewport?.removeEventListener("resize", measure);
    };
  }, [review]);
  useLayoutEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      const width = el.clientWidth,
        height = el.clientHeight,
        old = size.current;
      size.current = { width, height };
      if (
        ready.current &&
        old.width &&
        old.height &&
        (width !== old.width || height !== old.height)
      ) {
        const view = centeredView(
          { ...controller.current.getViewport(), ...old },
          width,
          height,
        );
        void controller.current.setViewport(view, { duration: 0 });
        saveView(key, view);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [key]);
  useEffect(() => {
    if (
      ready.current ||
      !rf.viewportInitialized ||
      (!initialized && count > 0) ||
      !canvas.current
    )
      return;
    ready.current = true;
    const width = canvas.current.clientWidth,
      height = canvas.current.clientHeight;
    size.current = { width, height };
    if (cached.current)
      void rf.setViewport(centeredView(cached.current, width, height), {
        duration: 0,
      });
    else if (count > 0)
      void rf.fitView({ padding: 0.2, maxZoom: 1.2, duration: 0 });
    // Initial display only. No edit, import, AI acceptance or undo fits the view.
  }, [initialized, count, rf.viewportInitialized]);
  const rememberView = (view: Viewport) => {
    if (ready.current) saveView(key, { ...view, ...size.current });
  };
  useEffect(
    () => () => {
      if (ready.current)
        saveView(key, { ...controller.current.getViewport(), ...size.current });
    },
    [key],
  );
  return {
    height,
    rememberView,
    initialViewport: cached.current ?? { x: 0, y: 0, zoom: 1 },
    recenter: () => rf.fitView({ padding: 0.2, maxZoom: 1.2, duration: 0 }),
  };
}
