import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./App.css";

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <main style={{ padding: 48, fontFamily: "sans-serif", maxWidth: 560, margin: "0 auto" }}>
          <h1>Something went wrong</h1>
          <p style={{ color: "#b91c1c" }}>{String(this.state.error?.message || this.state.error)}</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </main>
      );
    }
    return this.props.children;
  }
}

const el = document.getElementById("root");
if (!el) {
  throw new Error("main.jsx: #root element missing in index.html — app cannot mount.");
}

createRoot(el).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>
);
