import React from "react";
import ReactDOM from "react-dom/client";
import { ReactFlowProvider } from "reactflow";

import "reactflow/dist/style.css";
import "./index.css";
import App from "./App";
import { useStore } from "./store";
import { applyTheme } from "./utils";

// Apply the saved theme before the first paint to avoid a flash.
applyTheme(useStore.getState().darkMode);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ReactFlowProvider>
      <App />
    </ReactFlowProvider>
  </React.StrictMode>
);
