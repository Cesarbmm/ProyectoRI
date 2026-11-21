import { useLayoutEffect, useRef, useState } from "react";

export const reducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// FLIP: se mide antes y después del cambio de distribución. Solo se animan
// transform/opacity; no se duplica el formulario ni se anima el layout por frame.
export function useDockMotion(compact: boolean) {
  const logoRef = useRef<HTMLButtonElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const previous = useRef<DOMRect[]>([]);
  const animations = useRef<Animation[]>([]);
  const [moving, setMoving] = useState(false);
  const capture = () => {
    previous.current = [logoRef.current, barRef.current].map((el) =>
      el!.getBoundingClientRect(),
    );
    animations.current.forEach((animation) => animation.cancel());
  };
  useLayoutEffect(() => {
    let disposed = false;
    const before = previous.current;
    previous.current = [];
    if (!before.length || reducedMotion()) {
      setMoving(false);
      return;
    }
    const elements = [logoRef.current, barRef.current];
    const running = elements.flatMap((el, i) => {
      if (!el || before[i].width === 0) return [];
      const after = el.getBoundingClientRect();
      if (!after.width || !after.height) return [];
      return [
        el.animate(
          [
            {
              transformOrigin: "0 0",
              transform: `translate(${before[i].left - after.left}px, ${before[i].top - after.top}px) scale(${before[i].width / after.width}, ${before[i].height / after.height})`,
            },
            {
              transformOrigin: "0 0",
              transform: "translate(0, 0) scale(1, 1)",
            },
          ],
          { duration: 680, easing: "cubic-bezier(.22,.8,.2,1)", fill: "both" },
        ),
      ];
    });
    animations.current = running;
    setMoving(running.length > 0);
    void Promise.allSettled(
      running.map((animation) => animation.finished),
    ).then(() => {
      if (!disposed) {
        running.forEach((animation) => animation.cancel());
        setMoving(false);
      }
    });
    return () => {
      disposed = true;
      running.forEach((animation) => animation.cancel());
    };
  }, [compact]);
  return { logoRef, barRef, moving, capture };
}

// Mantiene el contenido anterior en el flujo mientras el scroll vuelve arriba.
export function scrollHome(done: () => void) {
  if (window.scrollY < 2 || reducedMotion()) {
    window.scrollTo({ top: 0, behavior: "instant" });
    done();
    return () => {};
  }
  let finished = false;
  const finish = () => {
    if (!finished) {
      finished = true;
      cleanup();
      done();
    }
  };
  const timer = window.setTimeout(finish, 900);
  const cleanup = () => {
    clearTimeout(timer);
    window.removeEventListener("scrollend", finish);
  };
  window.addEventListener("scrollend", finish, { once: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
  return () => {
    finished = true;
    cleanup();
  };
}
