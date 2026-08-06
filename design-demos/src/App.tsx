import { Routes, Route, Link, useLocation } from "react-router-dom";
import { useState, lazy, Suspense } from "react";

const Style1 = lazy(() => import("./style-1"));
const Style2 = lazy(() => import("./style-2"));
const Style3 = lazy(() => import("./style-3"));
const Style4 = lazy(() => import("./style-4"));

const styles = [
  { id: "style-1", name: "Cobalt Liquid Glass", desc: "Frosted glass surfaces, fluid depth, Apple Liquid Glass inspired", hue: "#246bfe" },
  { id: "style-2", name: "Linear Precision", desc: "Ultra-clean lines, tight rhythm, Linear/Notion inspired operational tool", hue: "#172033" },
  { id: "style-3", name: "Editorial Research", desc: "Serif-led typography, generous whitespace, publication-grade calm", hue: "#b94528" },
  { id: "style-4", name: "Bento Workspace", desc: "Layered bento grids, mixed cell depth, Apple bento inspired dashboard", hue: "#3159d8" },
];

function StyleSelector() {
  return (
    <div className="min-h-[100dvh] bg-background flex flex-col items-center justify-center p-8">
      <div className="max-w-3xl w-full">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground mb-2">
          ResearchMate design demos
        </h1>
        <p className="text-muted-foreground mb-10">
          Four design directions, same product surfaces. Pick one to explore.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {styles.map((s) => (
            <Link
              key={s.id}
              to={`/${s.id}`}
              className="group rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="flex items-center gap-3 mb-3">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ background: s.hue }}
                />
                <span className="font-semibold text-card-foreground">{s.name}</span>
              </div>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-sm text-primary opacity-0 transition-opacity group-hover:opacity-100">
                Explore →
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function DevBar() {
  const loc = useLocation();
  if (loc.pathname === "/") return null;
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-1 rounded-full border border-border bg-card/95 px-2 py-1.5 shadow-lg backdrop-blur">
      <Link to="/" className="rounded-full px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors">
        ← All demos
      </Link>
      {styles.map((s) => (
        <Link
          key={s.id}
          to={`/${s.id}`}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
            loc.pathname === `/${s.id}` ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
          }`}
        >
          {s.id.split("-")[1]}
        </Link>
      ))}
    </div>
  );
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<StyleSelector />} />
        <Route path="/style-1" element={<Suspense fallback={<div className="min-h-[100dvh] grid place-items-center text-muted-foreground">Loading…</div>}><Style1 /></Suspense>} />
        <Route path="/style-2" element={<Suspense fallback={<div className="min-h-[100dvh] grid place-items-center text-muted-foreground">Loading…</div>}><Style2 /></Suspense>} />
        <Route path="/style-3" element={<Suspense fallback={<div className="min-h-[100dvh] grid place-items-center text-muted-foreground">Loading…</div>}><Style3 /></Suspense>} />
        <Route path="/style-4" element={<Suspense fallback={<div className="min-h-[100dvh] grid place-items-center text-muted-foreground">Loading…</div>}><Style4 /></Suspense>} />
      </Routes>
      <DevBar />
    </>
  );
}
