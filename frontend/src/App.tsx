import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { About } from "./components/About";
import { Evaluation } from "./components/Benchmark";
import { Results } from "./components/Results";
import { SearchForm } from "./components/SearchForm";
import { useDockMotion, scrollHome } from "./lib/useDockMotion";
import { useEngine } from "./lib/useEngine";
import { useSearch } from "./lib/useSearch";
import { DEFAULT_MODEL, type ModelChoice, type ModelId } from "./lib/types";

type View = "search" | "evaluation" | "about";
const hashView = (): View =>
  ["#evaluation", "#evaluacion"].includes(location.hash)
    ? "evaluation"
    : ["#about", "#acerca"].includes(location.hash)
      ? "about"
      : "search";
export default function App() {
  const [view, setView] = useState<View>(hashView);
  const [choice, setChoice] = useState<ModelChoice>(DEFAULT_MODEL);
  const [compact, setCompact] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [outputHeight, setOutputHeight] = useState(0);
  const stageRef = useRef<HTMLElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const homeScroll = useRef<() => void>(() => {});
  const engine = useEngine();
  const search = useSearch();
  const motion = useDockMotion(compact);
  const labels = {
    checking: "Checking search engine…",
    ready: "Search engine connected",
    unavailable: "Search engine not ready",
    offline: "Server disconnected",
  };

  useLayoutEffect(() => {
    const observer = new ResizeObserver(() => {
      document.documentElement.style.setProperty(
        "--dock-height",
        `${stageRef.current?.getBoundingClientRect().height || 0}px`,
      );
    });
    if (stageRef.current) observer.observe(stageRef.current);
    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--dock-height");
    };
  }, []);
  useEffect(() => {
    const update = () => setView(hashView());
    window.addEventListener("popstate", update);
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener("hashchange", update);
      homeScroll.current();
    };
  }, []);
  useEffect(() => {
    if (
      view === "search" &&
      !motion.moving &&
      ["success", "error"].includes(search.state.status)
    ) {
      return scrollHome(() => setOutputHeight(0));
    }
  }, [search.state.status, search.state.rankings, motion.moving, view]);

  function navigate(next: View) {
    history.pushState(
      null,
      "",
      next === "evaluation"
        ? "#evaluation"
        : next === "about"
          ? "#about"
          : location.pathname,
    );
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
    requestAnimationFrame(() =>
      document
        .querySelector<HTMLElement>(
          next === "search" ? "#query" : ".page-section h1",
        )
        ?.focus({ preventScroll: true }),
    );
  }
  function home() {
    homeScroll.current();
    homeScroll.current = scrollHome(() => {
      motion.capture();
      search.cancel();
      setCompact(false);
      setChoice(DEFAULT_MODEL);
      setResetToken((value) => value + 1);
      setOutputHeight(0);
      navigate("search");
    });
  }
  function run(
    query: string,
    model: ModelChoice,
    topK: number,
    comparison: ModelId[] | null,
  ) {
    homeScroll.current();
    setOutputHeight(outputRef.current?.getBoundingClientRect().height || 0);
    if (!compact) {
      motion.capture();
      setCompact(true);
    }
    void search.run(query, model, topK, comparison);
  }

  return (
    <div className={`app-shell ${compact ? "is-compact" : "is-home"}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="ambient" aria-hidden="true">
        <span />
        <span />
      </div>
      <main id="main" tabIndex={-1}>
        <div className="search-view" hidden={view !== "search"}>
          <section
            ref={stageRef}
            className="search-stage"
            data-moving={motion.moving}
            aria-label="FiQA search"
          >
            <div className="search-dock">
              <h1 className="wordmark">
                <button
                  ref={motion.logoRef}
                  className="brand-home"
                  type="button"
                  aria-label="FiQA, back to home"
                  aria-describedby="brand-caption"
                  onClick={home}
                >
                  <span className="brand-word">
                    F<span className="brand-i">i</span>QA
                  </span>
                  <span className="orbit" aria-hidden="true" />
                  <span id="brand-caption" className="brand-caption">
                    Financial Search
                  </span>
                </button>
              </h1>
              <SearchForm
                models={engine.models}
                connected={engine.status === "ready"}
                busy={search.state.status === "loading"}
                compact={compact}
                resetToken={resetToken}
                barRef={motion.barRef}
                choice={choice}
                onChoice={setChoice}
                onSearch={run}
              />
              {(engine.status === "offline" ||
                engine.status === "unavailable") && (
                <div className="connection-error" role="alert">
                  <p>{engine.error}</p>
                  <button type="button" onClick={() => void engine.refresh()}>
                    Reconnect
                  </button>
                </div>
              )}
            </div>
          </section>
          <div
            ref={outputRef}
            className="search-output"
            style={{ minHeight: outputHeight || undefined }}
          >
            {!motion.moving && (
              <Results
                state={search.state}
                cancel={() => {
                  search.cancel();
                  setOutputHeight(0);
                }}
              />
            )}
          </div>
        </div>
        {view !== "search" && (
          <button
            className="page-home brand-word"
            type="button"
            onClick={home}
            aria-label="FiQA, back to home"
          >
            FiQA
          </button>
        )}
        {view === "evaluation" && <Evaluation />}
        {view === "about" && <About />}
      </main>
      <footer className="site-footer">
        <span className={`engine-status ${engine.status}`} role="status">
          <i aria-hidden="true" />
          {labels[engine.status]}
        </span>
        <nav aria-label="Footer navigation">
          {view !== "search" && (
            <a
              href="#search"
              onClick={(event) => {
                event.preventDefault();
                navigate("search");
              }}
            >
              Search
            </a>
          )}
          <a
            href="#evaluation"
            aria-current={view === "evaluation" ? "page" : undefined}
            onClick={(event) => {
              event.preventDefault();
              navigate("evaluation");
            }}
          >
            Evaluation
          </a>
          <a
            href="#about"
            aria-current={view === "about" ? "page" : undefined}
            onClick={(event) => {
              event.preventDefault();
              navigate("about");
            }}
          >
            About the system
          </a>
        </nav>
      </footer>
    </div>
  );
}
