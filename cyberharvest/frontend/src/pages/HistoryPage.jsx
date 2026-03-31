import React, { useState, useEffect } from "react";
import ApiPanel from "../components/ApiPanel";
import ResultCard from "../components/ResultCard";

export default function HistoryPage({ backendUrl }) {
  const [history, setHistory]       = useState([]);
  const [selected, setSelected]     = useState(null);
  const [detail, setDetail]         = useState(null);
  const [loading, setLoading]       = useState(false);
  const [showAll, setShowAll]       = useState(false);

  const PREVIEW_COUNT = 10;

  const fetchHistory = async () => {
    try {
      const r = await fetch(`${backendUrl}/api/search/history`);
      setHistory(await r.json());
    } catch (e) {
      console.error("获取历史失败", e);
    }
  };

  const fetchDetail = async (search_id) => {
    setLoading(true);
    setDetail(null);
    try {
      const r = await fetch(`${backendUrl}/api/search/result/${search_id}`);
      setDetail(await r.json());
    } catch (e) {
      console.error("获取详情失败", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    const timer = setInterval(fetchHistory, 5000);
    return () => clearInterval(timer);
  }, []);

  const displayed = showAll ? history : history.slice(0, PREVIEW_COUNT);

  const statusColor = (s) => ({ done: "#60c060", running: "#f0c040", error: "#e06060" }[s] || "#888");
  const statusText  = (s) => ({ done: "完成", running: "采集中", error: "失败" }[s] || s);

  const formatTime = (ts) => {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,"0")}`;
  };

  return (
    <div className="history-page">
      <div className="history-list">
        <div className="history-header">
          <h2>搜索历史</h2>
          <button className="btn-secondary" onClick={fetchHistory}>刷新</button>
        </div>

        {history.length === 0 && (
          <div className="empty-tip">暂无搜索记录</div>
        )}

        {displayed.map(item => (
          <div
            key={item.search_id}
            className={`history-item ${selected === item.search_id ? "active" : ""}`}
            onClick={() => { setSelected(item.search_id); fetchDetail(item.search_id); }}
          >
            <div className="history-item-top">
              <span className="history-keyword">{item.keyword}</span>
              <span className="history-status" style={{ color: statusColor(item.status) }}>
                {statusText(item.status)}
              </span>
            </div>
            <div className="history-item-bottom">
              <span className="history-id">{item.search_id}</span>
              <span className="history-meta">{item.count} 条 · {formatTime(item.created_at)}</span>
            </div>
          </div>
        ))}

        {history.length > PREVIEW_COUNT && (
          <button className="btn-expand" onClick={() => setShowAll(!showAll)}>
            {showAll ? "收起" : `展开全部 (${history.length} 条)`}
          </button>
        )}
      </div>

      <div className="history-detail">
        {!selected && (
          <div className="empty-tip">← 点击左侧记录查看详情</div>
        )}
        {loading && <div className="status-bar">加载中...</div>}
        {detail && !loading && (
          <>
            <ApiPanel backendUrl={backendUrl} searchId={detail.search_id} keyword={detail.keyword} />
            <div className="results">
              {detail.results?.map((r, i) => <ResultCard key={i} data={r} />)}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
