import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { LadderPage } from "./ladder/LadderPage";
import { LivePage } from "./live/LivePage";
import "./index.css";

const path = window.location.pathname;
const demo = new URLSearchParams(window.location.search).has("demo");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {path === "/live" ? (
      <LivePage demo={demo} />
    ) : path === "/ladder" ? (
      <LadderPage />
    ) : (
      <App demo={demo} />
    )}
  </StrictMode>,
);
