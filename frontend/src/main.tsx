import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { LivePage } from "./live/LivePage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {window.location.pathname === "/live" ? (
      <LivePage
        demo={new URLSearchParams(window.location.search).has("demo")}
      />
    ) : (
      <App />
    )}
  </StrictMode>,
);
