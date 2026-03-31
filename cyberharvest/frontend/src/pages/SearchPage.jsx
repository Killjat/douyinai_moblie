import React, { useState, useRef, useEffect } from "react";
import ResultCard from "../components/ResultCard";
import ApiPanel from "../components/ApiPanel";

export default function SearchPage({ backendUrl, currentSearchId, onSearchIdChange }) {
  const [keyword, setKeyword]         = useState("");
  const [count, setCount]             = useState(20);
  const [maxComments, setMaxComments] = useState(5);
  const [latest, setLatest]           = useState(false);
  const [mode, setMode]               = useState("direct"); // "direct" | "select"

  // 直接采集模式
  const [results, setResults]   = useState([]);
  const [running, setRunning]   = useState(false);
  const [status, setStatus]     = useState("");
  const [searchId, setSearchId] = useState("");

  // 选择采集模式
  const [scanItems, setScanItems]     = useState([]);
  const [selected, setSelected]       = useState(new Set());
  const [scanning, setScanning]       = useState(false);
  const [collecting, setCollecting]   = useState(false);
  const [scanId, setScanId]           = useState("");

  // 结果内搜索
  const [filter, setFilter] = useState("");

  const filteredResults = filter.trim()
    ? results.filter(r => {
        const q = filter.toLowerCase();
        return (
          (r.nickname || "").toLowerCase().includes(q) ||
          (r.title || "").toLowerCase().includes(q) ||
          (r.author_handle || "").toLowerCase().includes(q) ||
          (r.comments || []).some(c =>
            (c.content || "").toLowerCase().includes(q) ||
            (c.user || "").toLowerCase().includes(q)
          )
        );
      })
    : results;

  useEffect(() => {
    if (!currentSearchId || currentSearchId === searchId) return;
    loadHistory(currentSearchId);
  }, [currentSearchId]);

  const loadHistory = async (id) => {
    try {
      const r = await fetch(`${backendUrl}/api/search/result/${id}`);
      const data = await r.json();
      setSearchId(id); setKeyword(data.keyword);
      setResults(data.results || []);
      setStatus(`已加载：${data.keyword}，共 ${data.count} 条`);
      onSearchIdChange(id);
    } catch (e) { setStatus(`加载失败: ${e.message}`); }
  };

  // 直接采集
  const startDirect = async () => {
    if (!keyword.trim()) return;
    setResults([]); setSearchId(""); setRunning(true); setStatus("采集中...");
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const resp = await fetch(`${backendUrl}/api/search/stream`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, count, max_comments: maxComments, latest }),
        signal: ctrl.signal,
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder(); let buf = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const msg = JSON.parse(line.slice(5).trim());
          if (msg.type === "search_id") { setSearchId(msg.search_id); onSearchIdChange(msg.search_id); }
          else if (msg.type === "result") { setResults(prev => [...prev, msg.data]); setStatus(`已采集: ${(msg.data.title || "").slice(0, 25)}`); }
          else if (msg.type === "done") setStatus(`完成，共 ${msg.total} 条`);
          else if (msg.type === "error") setStatus(`错误: ${msg.msg}`);
        }
      }
    } catch (e) { if (e.name !== "AbortError") setStatus(`连接失败: ${e.message}`); }
    finally { setRunning(false); }
  };

  // 第一步：扫描列表
  const startScan = async () => {
    if (!keyword.trim()) return;
    setScanItems([]); setSelected(new Set()); setScanning(true); setStatus("扫描列表中...");
    try {
      const r = await fetch(`${backendUrl}/api/search/scan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, count, latest }),
      });
      const data = await r.json();
      setScanId(data.scan_id); setScanItems(data.items || []);
      setStatus(`扫描完成，共 ${data.count} 条，请选择要采集的视频`);
    } catch (e) { setStatus(`扫描失败: ${e.message}`); }
    finally { setScanning(false); }
  };

  // 第二步：采集选中
  const startCollect = async () => {
    if (selected.size === 0) return;
    setResults([]); setCollecting(true); setStatus("采集中...");
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const resp = await fetch(`${backendUrl}/api/search/collect`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scan_id: scanId, titles: [...selected], max_comments: maxComments }),
        signal: ctrl.signal,
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder(); let buf = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const msg = JSON.parse(line.slice(5).trim());
          if (msg.type === "search_id") { setSearchId(msg.search_id); onSearchIdChange(msg.search_id); }
          else if (msg.type === "result") { setResults(prev => [...prev, msg.data]); setStatus(`已采集: ${(msg.data.title || "").slice(0, 25)}`); }
          else if (msg.type === "done") setStatus(`完成，共 ${msg.total} 条`);
          else if (msg.type === "error") setStatus(`错误: ${msg.msg}`);
        }
      }
    } catch (e) { if (e.name !== "AbortError") setStatus(`连接失败: ${e.message}`); }
    finally { setCollecting(false); }
  };

  const stop = () => { abortRef.current?.abort(); setRunning(false); setCollecting(false); setStatus("已停止"); };

  const toggleSelect = (title) => {
    setSelected(prev => {
      const s = new Set(prev);
      s.has(title) ? s.delete(title) : s.add(title);
      return s;
    });
  };
  const selectAll = () => setSelected(new Set(scanItems.map(i => i.title)));
  const clearAll  = () => setSelected(new Set());

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `${keyword}_${Date.now()}.json`; a.click();
  };
  const downloadTXT = () => {
    const txt = results.map(r =>
      `作者: ${r.nickname}\n标题: ${r.title}\n点赞: ${r.likes}  评论: ${r.comment_count}\n${"─".repeat(40)}`
    ).join("\n\n");
    const blob = new Blob([txt], { type: "text/plain" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `${keyword}_${Date.now()}.txt`; a.click();
  };

  const isRunning = running || scanning || collecting;

  return (
    <div className="search-page">
      <div className="search-bar">
        <input className="keyword-input" placeholder="输入搜索关键词..."
          value={keyword} onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !isRunning && (mode === "direct" ? startDirect() : startScan())}
        />
        <div className="search-options">
          <label>数量 <input type="number" min={1} max={100} value={count} onChange={e => setCount(+e.target.value)} /></label>
          <label>评论 <input type="number" min={0} max={50} value={maxComments} onChange={e => setMaxComments(+e.target.value)} /></label>
          <label><input type="checkbox" checked={latest} onChange={e => setLatest(e.target.checked)} /> 最新</label>
          <div className="mode-toggle">
            <button className={mode === "direct" ? "active" : ""} onClick={() => setMode("direct")}>直接采集</button>
            <button className={mode === "select" ? "active" : ""} onClick={() => setMode("select")}>先选后采</button>
          </div>
        </div>
        <div className="search-actions">
          {!isRunning ? (
            mode === "direct"
              ? <button className="btn-primary" onClick={startDirect}>开始采集</button>
              : <button className="btn-primary" onClick={startScan}>扫描列表</button>
          ) : (
            <button className="btn-danger" onClick={stop}>停止</button>
          )}
          {results.length > 0 && <>
            <button className="btn-secondary" onClick={downloadJSON}>下载 JSON</button>
            <button className="btn-secondary" onClick={downloadTXT}>下载 TXT</button>
          </>}
        </div>
      </div>

      {status && <div className="status-bar">{status}</div>}

      {/* 选择模式：扫描结果列表 */}
      {mode === "select" && scanItems.length > 0 && (
        <div className="scan-list">
          <div className="scan-list-header">
            <span>选择要采集的视频 ({selected.size}/{scanItems.length})</span>
            <div>
              <button className="btn-secondary" onClick={selectAll}>全选</button>
              <button className="btn-secondary" onClick={clearAll}>清空</button>
              {selected.size > 0 && !collecting && (
                <button className="btn-primary" onClick={startCollect}>
                  采集选中 ({selected.size})
                </button>
              )}
            </div>
          </div>
          {scanItems.map((item, i) => (
            <div key={i} className={`scan-item ${selected.has(item.title) ? "selected" : ""}`}
              onClick={() => toggleSelect(item.title)}>
              <input type="checkbox" checked={selected.has(item.title)} onChange={() => {}} />
              <div className="scan-item-info">
                <span className="scan-nickname">@{item.nickname || "?"}</span>
                <span className="scan-title">{item.title}</span>
              </div>
              <div className="scan-item-stats">
                <span>❤️ {item.likes}</span>
                <span>💬 {item.comment_count}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {searchId && <ApiPanel backendUrl={backendUrl} searchId={searchId} keyword={keyword} />}

      {results.length > 0 && (
        <div className="filter-bar">
          <input
            className="filter-input"
            placeholder={`在 ${results.length} 条结果中搜索...`}
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
          {filter && (
            <span className="filter-count">
              {filteredResults.length} / {results.length}
            </span>
          )}
        </div>
      )}

      <div className="results">
        {filteredResults.map((r, i) => <ResultCard key={i} data={r} />)}
      </div>
    </div>
  );
}
