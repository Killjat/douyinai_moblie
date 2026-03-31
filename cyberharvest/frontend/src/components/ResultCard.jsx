import React, { useState } from "react";

export default function ResultCard({ data }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="result-card">
      <div className="card-header" onClick={() => setExpanded(!expanded)}>
        <div className="card-meta">
          <span className="nickname">@{data.nickname}</span>
          <span className="date">{data.date}</span>
        </div>
        <div className="card-title">{data.title}</div>
        <div className="card-stats">
          <span>❤️ {data.likes}</span>
          <span>💬 {data.comment_count}</span>
          <span>↗️ {data.shares}</span>
          {data.music && <span>🎵 {data.music}</span>}
        </div>
      </div>

      {expanded && (
        <div className="card-body">
          {data.cover && (
            <img src={`file://${data.cover}`} alt="封面" className="cover-img" />
          )}
          {data.comments?.length > 0 && (
            <div className="comments">
              <div className="comments-title">评论 ({data.comment_count})</div>
              {data.comments.map((c, i) => (
                <div key={i} className="comment-item">
                  <span className="comment-user">{c.user}</span>
                  <span className="comment-content">{c.content}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
