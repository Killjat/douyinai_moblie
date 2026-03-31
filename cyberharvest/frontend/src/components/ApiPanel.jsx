import React, { useState } from "react";

export default function ApiPanel({ backendUrl, searchId, keyword }) {
  const [lang, setLang] = useState("curl");

  const apiUrl = `${backendUrl}/api/search/result/${searchId}`;

  const examples = {
    curl: `curl "${apiUrl}"`,
    python: `import requests

resp = requests.get("${apiUrl}")
data = resp.json()

print(f"关键词: {data['keyword']}")
print(f"采集数量: {data['count']}")
for item in data['results']:
    print(item['nickname'], item['title'][:30])`,
    js: `const resp = await fetch("${apiUrl}");
const data = await resp.json();

console.log(\`关键词: \${data.keyword}\`);
data.results.forEach(item => {
  console.log(item.nickname, item.title);
});`,
  };

  const download = () => {
    const content = `# CyberHarvest API 调用示例
# 搜索关键词: ${keyword}
# Search ID: ${searchId}
# API 地址: ${apiUrl}

## cURL
${examples.curl}

## Python
${examples.python}

## JavaScript
${examples.js}
`;
    const blob = new Blob([content], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `api_${searchId}.txt`;
    a.click();
  };

  return (
    <div className="api-panel">
      <div className="api-panel-header">
        <div className="api-panel-title">
          🔗 API 调用
          <span className="search-id-badge">{searchId}</span>
        </div>
        <div className="api-panel-actions">
          <div className="lang-tabs">
            {["curl", "python", "js"].map(l => (
              <button key={l} className={lang === l ? "active" : ""} onClick={() => setLang(l)}>
                {l === "js" ? "JavaScript" : l.charAt(0).toUpperCase() + l.slice(1)}
              </button>
            ))}
          </div>
          <button className="btn-secondary" onClick={download}>下载调用文档</button>
        </div>
      </div>
      <pre className="api-code">{examples[lang]}</pre>
    </div>
  );
}
