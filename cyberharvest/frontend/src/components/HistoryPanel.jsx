import React, { useState, useEffect } from "react";

export default function HistoryPanel({ backendUrl, onSelect, currentSearchId }) {
  const [history, setHistory] = useState([]);
  const [expanded, setExpanded] = useState(false);

  const fetchHistory = async () => {
    try {
      const r = await fetch(`${backendUrl}/api/search/history`);
      setHistory(await r.json());
    } catch (_) {}
  };

  useEffect(() => {
    fetchHistory();
    const timer = setInterval(fetchHistory, 3000);
    return () => clearInterval(timer);
  }, [backendUrl]);

  const visible = expanded ? history : history.slice(0, 10);
  const hasMore = history.length > 10;

  const statusColor = { done: "#60c060", running: "#f0c040", error: "#e06060" };
  const statusLabel = { done: "完成", running: "采集中", error: "失败" };

  return (
    <div className="history-panel">
      <div className="history-header">
        <span>搜索历史</span>
        <span className="history-count">{history.length}</span>
      </div>

      <div className="history-list">
        {visible.length === 0 && (
          <div className="history-empty">暂无搜索记录</div>
        )}
        {visible.map(item => (
          <div
            key={item.search_id}
            className={`history-item ${item.search_id === currentSearchId ? "active" : ""}`}
            onClick={() => onSelect(item.search_id)}
          >
            <div className="history-item-top">
              <span className="history-keyword">{item.keyword}</span>
              <span className="history-status" style={{ color: statusColor[item.status] }}>
                {statusLabel[item.status] || item.status}
              </span>
            </div>
            <div className="history-item-bottom">
              <span className="history-id">{item.search_id}</span>
              <span className="history-count-badge">{item.count} 条</span>
            </div>
          </div>
        ))}
      </div>

      {hasMore && (
        <button className="history-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? "收起" : `查看全部 ${history.length} 条`}
        </button>
      )}
    </div>
  );
}
