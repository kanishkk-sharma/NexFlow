import { useEffect, useState } from "react";

import { AnalyzeDialog } from "./AnalyzeDialog";
import { AuthScreen } from "./AuthScreen";
import { Header } from "./Header";
import { ResultsPanel } from "./ResultsPanel";
import { useStore } from "./store";
import { Toasts } from "./Toasts";
import { PipelineToolbar } from "./toolbar";
import { PipelineUI } from "./ui";
import { applyTheme, isEditableTarget } from "./utils";
import { WorkflowManager } from "./WorkflowManager";

function App() {
  const authReady = useStore((s) => s.authReady);
  const token = useStore((s) => s.token);
  const darkMode = useStore((s) => s.darkMode);
  const dirty = useStore((s) => s.dirty);
  const initApp = useStore((s) => s.initApp);
  const [managerOpen, setManagerOpen] = useState(false);

  useEffect(() => {
    initApp();
  }, [initApp]);

  useEffect(() => {
    applyTheme(darkMode);
  }, [darkMode]);

  // Warn before closing the tab with unsaved work.
  useEffect(() => {
    if (!dirty || !token) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty, token]);

  // Keyboard shortcuts.
  useEffect(() => {
    if (!token) return undefined;
    const onKeyDown = (event) => {
      const mod = event.ctrlKey || event.metaKey;
      if (!mod) return;
      const key = event.key.toLowerCase();
      const state = useStore.getState();
      if (key === "s") {
        event.preventDefault();
        state.saveWorkflow();
      } else if (key === "enter") {
        event.preventDefault();
        state.runWorkflow();
      } else if ((key === "z" || key === "y") && !isEditableTarget(event.target)) {
        event.preventDefault();
        if (key === "y" || event.shiftKey) state.redo();
        else state.undo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [token]);

  if (!authReady) return <div className="nf-splash">Loading NexFlow…</div>;

  if (!token) {
    return (
      <>
        <AuthScreen />
        <Toasts />
      </>
    );
  }

  return (
    <div className="nf-app">
      <Header onOpenManager={() => setManagerOpen(true)} />
      <PipelineToolbar />
      <main className="nf-canvas">
        <PipelineUI />
      </main>
      <ResultsPanel />
      {managerOpen && <WorkflowManager onClose={() => setManagerOpen(false)} />}
      <AnalyzeDialog />
      <Toasts />
    </div>
  );
}

export default App;
