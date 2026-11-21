import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { ModelsInfo } from "./types";

export function useEngine() {
  const [state, setState] = useState<{
    status: "checking" | "ready" | "offline" | "unavailable";
    models?: ModelsInfo;
    error?: string;
  }>({ status: "checking" });
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async (silent = false) => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    if (!silent) setState({ status: "checking" });
    try {
      const [, , models] = await Promise.all([
        api.health(controller.signal),
        api.ready(controller.signal),
        api.models(controller.signal),
      ]);
      if (!controller.signal.aborted) setState({ status: "ready", models });
    } catch (error) {
      if (!controller.signal.aborted)
        setState({
          status:
            error instanceof ApiError && error.status === 503
              ? "unavailable"
              : "offline",
          error: (error as Error).message,
        });
    }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      void refresh(true);
    }, 30_000);
    const online = () => {
      void refresh();
    };
    const offline = () => {
      active.current?.abort();
      setState({
        status: "offline",
        error: "There is no network connection. Reconnect to search.",
      });
    };
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    return () => {
      clearInterval(interval);
      active.current?.abort();
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
    };
  }, [refresh]);
  return { ...state, refresh };
}
