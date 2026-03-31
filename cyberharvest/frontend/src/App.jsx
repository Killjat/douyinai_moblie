import React, { useState, useEffect } from "react";
import SearchPage from "./pages/SearchPage";
import DepsPage from "./pages/DepsPage";
import "./App.css";

export default function App() {
  const [page, setPage] = useState("search");
  const [backendUrl, setBackendUrl] = useState("http://127.0.0.1:18765");

  useEffect(() => {
    if (window.electron) {
      window.electron.getBackendUrl().then(setBackendUrl);
    }
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">🌾 CyberHarvest</div>
        <nav>
          <button className={page === "search" ? "active" : ""} onClick={() => setPage("search")}>
            搜索采集
          </button>
          <button className={page === "deps" ? "active" : ""} onClick={() => setPage("deps")}>
            系统检测
          </button>
        </nav>
      </aside>
      <main className="content">
        {page === "search" && <SearchPage backendUrl={backendUrl} />}
        {page === "deps"   && <DepsPage   backendUrl={backendUrl} />}
      </main>
    </div>
  );
}
