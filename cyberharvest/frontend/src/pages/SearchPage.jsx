import React, { useState, useRef } from "react";
import ResultCard from "../components/ResultCard";

export default function SearchPage({ backendUrl }) {
  const [keyword, setKeyword]     = useState("");
  const [count, setCount]         = useState(10);
  const [maxComments, setMaxComments] = useState(5);
  const [latest, setLatest]       = useState(false);
  const [results, setResults]     = useState([]);
  const [running, setRunning]     = useState(false);
  const [status, setStatus]       = useState("");
  const abortRef = useRef(null);

  const start = async () => {
    if (!keyword.trim()) return;
    setResults([]);
    setRunning(true);
    setStatus("采集中...");

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await fetch(`${backendUrl}/api/search/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, count, max_comments: maxComments, latest }),
        signal: ctrl.signal,
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const msg = JSON.parse(line.slice(5).trim());
          if (msg.type === "result") {
            setResults(prev => [...prev, msg.data]);
            setStatus(`已采集 ${msg.data.nickname || ""}: ${(msg.data.title || "").slice(0, 20)}`);
          } else if (msg.type === "done") {
            setStatus(`完成，共 ${msg.total} 条`);
          } else if (msg.type === "error") {
            setStatus(`错误: ${msg.msg}`);
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") setStatus(`连接失败: ${e.message}`);
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
    setStatus("已停止");
  };

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${keyword}_${Date.now()}.json`;
    a.click();
  };

  const downloadTXT = () => {
    const txt = results.map(r =>
      `作者: ${r.nickname}\n标题: ${r.title}\n点赞: ${r.likes}  评论: ${r.comment_count}  分享: ${r.shares}\n日期: ${r.date}\n${"─".repeat(40)}`
    ).join("\n\n");
    const blob = new Blob([txt], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${keyword}_${Date.now()}.txt`;
    a.click();
  };

  return (
    <div className="search-page">
      <div className="search-bar">
        <input
          className="keyword-input"
          placeholder="输入搜索关键词..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !running && start()}
        />
        <div className="search-options">
          <label>数量 <input type="number" min={1} max={100} value={count} onChange={e => setCount(+e.target.value)} /></label>
          <label>评论 <input type="number" min={0} max={50} value={maxComments} onChange={e => setMaxComments(+e.target.value)} /></label>
          <label><input type="checkbox" checked={latest} onChange={e => setLatest(e.target.checked)} /> 最新</label>
        </div>
        <div className="search-actions">
          {!running
            ? <button className="btn-primary" onClick={start}>开始采集</button>
            : <button className="btn-danger"  onClick={stop}>停止</button>
          }
          {results.length > 0 && <>
            <button className="btn-secondary" onClick={downloadJSON}>下载 JSON</button>
            <button className="btn-secondary" onClick={downloadTXT}>下载 TXT</button>
          </>}
        </div>
      </div>

      {status && <div className="status-bar">{status}</div>}

      <div className="results">
        {results.map((r, i) => <ResultCard key={i} data={r} />)}
      </div>
    </div>
  );
}
