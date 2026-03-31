import React, { useState, useEffect } from "react";

const DEP_LABELS = {
  adb:          { label: "ADB",           desc: "Android 调试工具" },
  "agent-device": { label: "agent-device", desc: "设备控制工具" },
  node:         { label: "Node.js",       desc: "JavaScript 运行时" },
  python3:      { label: "Python 3",      desc: "Python 运行时" },
  adbkeyboard:  { label: "ADBKeyboard",   desc: "中文输入法 APK" },
  device:       { label: "Android 设备",  desc: "已连接的手机" },
};

export default function DepsPage({ backendUrl }) {
  const [deps, setDeps]       = useState({});
  const [loading, setLoading] = useState(false);
  const [msg, setMsg]         = useState("");

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

  const install = async (dep) => {
    setMsg(`正在安装 ${dep}...`);
    const endpoint = dep === "adbkeyboard"
      ? `${backendUrl}/api/system/install-apk`
      : `${backendUrl}/api/system/install/${dep}`;
    const r = await fetch(endpoint, { method: "POST" });
    const data = await r.json();
    setMsg(data.ok ? `✅ ${dep} 安装成功` : `❌ ${data.msg}`);
    check();
  };

  return (
    <div className="deps-page">
      <div className="deps-header">
        <h2>系统依赖检测</h2>
        <button className="btn-secondary" onClick={check} disabled={loading}>
          {loading ? "检测中..." : "重新检测"}
        </button>
      </div>
      {msg && <div className="status-bar">{msg}</div>}
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
              {!ok && ["agent-device", "adbkeyboard"].includes(key) && (
                <button className="btn-install" onClick={() => install(key)}>
                  一键安装
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
