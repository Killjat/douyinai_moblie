import React, { useState, useEffect } from "react";

const DEP_LABELS = {
  adb:            { label: "ADB",           desc: "Android 调试工具" },
  "agent-device": { label: "agent-device",  desc: "设备控制工具" },
  node:           { label: "Node.js",       desc: "JavaScript 运行时" },
  python3:        { label: "Python 3",      desc: "Python 运行时" },
  adbkeyboard:    { label: "ADBKeyboard",   desc: "中文输入法 APK" },
  device:         { label: "Android 设备",  desc: "已连接的手机" },
};

const STATUS_COLOR = { ok: "#60c060", skip: "#60c060", running: "#f0c040", fail: "#e06060", warn: "#f0a040", done: "#60c060" };
const STATUS_ICON  = { ok: "✅", skip: "✅", running: "⏳", fail: "❌", warn: "⚠️", done: "🎉" };

export default function DepsPage({ backendUrl }) {
  const [deps, setDeps]         = useState({});
  const [loading, setLoading]   = useState(false);
  const [installing, setInstalling] = useState(false);
  const [logs, setLogs]         = useState([]);
  const [msg, setMsg]           = useState("");

  const check = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${backendUrl}/api/system/deps`);
      setDeps(await r.json());
    } catch (e) {
      setMsg("后端未启动，请稍候重试");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { check(); }, []);

  const allOk = Object.entries(DEP_LABELS)
    .filter(([k]) => k !== "device")
    .every(([k]) => deps[k]?.ok);

  const installAll = async () => {
    setInstalling(true);
    setLogs([]);
    setMsg("");
    try {
      const resp = await fetch(`${backendUrl}/api/system/install-all`, { method: "POST" });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          setLogs(prev => [...prev, evt]);
          if (evt.status === "done") { check(); setInstalling(false); }
        }
      }
    } catch (e) {
      setMsg(`安装失败: ${e.message}`);
      setInstalling(false);
    }
  };

  const installApk = async () => {
    setMsg("正在安装 ADBKeyboard...");
    const r = await fetch(`${backendUrl}/api/system/install-apk`, { method: "POST" });
    const data = await r.json();
    setMsg(data.ok ? "✅ ADBKeyboard 安装成功" : `❌ ${data.msg}`);
    check();
  };

  return (
    <div className="deps-page">
      <div className="deps-header">
        <h2>系统依赖检测</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-secondary" onClick={check} disabled={loading}>
            {loading ? "检测中..." : "重新检测"}
          </button>
          {!allOk && (
            <button className="btn-primary" onClick={installAll} disabled={installing}>
              {installing ? "安装中..." : "一键安装全部"}
            </button>
          )}
        </div>
      </div>

      {msg && <div className="status-bar">{msg}</div>}

      {/* 安装进度日志 */}
      {logs.length > 0 && (
        <div className="install-log">
          {logs.map((log, i) => (
            <div key={i} className="install-log-item">
              <span>{STATUS_ICON[log.status] || "•"}</span>
              <span style={{ color: STATUS_COLOR[log.status], fontWeight: 600, minWidth: 100 }}>
                {log.step}
              </span>
              <span className="install-log-msg">{log.msg}</span>
            </div>
          ))}
        </div>
      )}

      <div className="deps-list">
        {Object.entries(DEP_LABELS).map(([key, { label, desc }]) => {
          const info = deps[key];
          const ok = info?.ok;
          return (
            <div key={key} className={`dep-item ${ok ? "ok" : "fail"}`}>
              <div className="dep-icon">{ok ? "✅" : "❌"}</div>
              <div className="dep-info">
                <div className="dep-name">{label}</div>
                <div className="dep-desc">{desc}</div>
                {info?.version && <div className="dep-version">{info.version}</div>}
              </div>
              {!ok && key === "adbkeyboard" && (
                <button className="btn-install" onClick={installApk}>安装 APK</button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
