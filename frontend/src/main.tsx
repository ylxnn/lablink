import React from "react";
import ReactDOM from "react-dom/client";
import App from "./lab/App";
import "./lab/style.css";
import "./lab/theme.css";
import { installEffects } from "./lab/effects";
installEffects();
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
