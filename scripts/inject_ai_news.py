#!/usr/bin/env python3
"""Quick AI News Injection - supports all formats"""
import re
from pathlib import Path

AI_NEWS_DIR = Path.home() / ".openclaw/workspace/skills/ai-news-zh/outputs"
INDEX_HTML = Path.home() / ".openclaw/workspace/daynews/docs/index.html"

# 获取最新文件
files = sorted(AI_NEWS_DIR.glob("*.md"), reverse=True, key=lambda p: p.stat().st_mtime)
if not files:
    print("❌ 没有找到 AI 新闻文件")
    exit(1)

content = files[0].read_text(encoding='utf-8')
items = []

# 格式1：### 标题 + **关键词**
matches = list(re.finditer(
    r'###\s+(.+?)\n\*\*(.+?)\*\*\n-\s+🔗\s+来源：\[(.+?)\]\((.+?)\)\n-\s+📅\s+时间：(.+?)\n\n(.+?)(?:\n\n\*\*标签\*\*：(.+?))?(?=\n\n---|\n\n###|\n\n##|\Z)',
    content, re.DOTALL
))

for idx, m in enumerate(matches):
    title, keywords, source, link, time, summary, tags = m.groups()
    combined = (tags or "") + " " + keywords + " " + summary
    
    # 智能分类
    emoji = "🤖"
    if "融资" in combined or "funding" in combined.lower():
        emoji = "💰"
    elif "模型" in combined or "model" in combined.lower() or "memory" in combined.lower():
        emoji = "🧠"
    elif "监管" in combined or "政策" in combined:
        emoji = "🛡️"
    
    items.append({
        "title": title.strip(),
        "summary": summary.strip()[:180],
        "link": link.strip(),
        "emoji": emoji
    })
    if len(items) >= 12:
        break

print(f"✅ 解析到 {len(items)} 条新闻")

if items:
    # 生成简单版 HTML（不用轮播）
    html = f'<section class="card"><h2><span>🤖 AI 新闻</span><span class="badge">{len(items)}</span></h2><div class="tlist">\n'
    for it in items[:8]:
        html += f'<div class="titem"><a class="ttitle" href="{it["link"]}" target="_blank">{it["emoji"]} {it["title"]}</a>'
        html += f'<div style="margin-top:4px;color:var(--muted);font-size:13px">{it["summary"]}...</div></div>\n'
    html += '</div></section>\n'
    
    # 读取并更新 index.html
    page = INDEX_HTML.read_text(encoding='utf-8')
    
    # 删除所有现有 AI 新闻
    page = re.sub(r'<section class="card[^"]*"[^>]*>\s*<h2[^>]*>\s*<span>🤖 AI 新闻.*?</section>\s*', '', page, flags=re.DOTALL)
    
    # 插入新版本
    page = re.sub(
        r'(</section>)(\s*<div class="grid3">)',
        f'\\1\n\n      {html}\\2',
        page,
        count=1
    )
    
    INDEX_HTML.write_text(page, encoding='utf-8')
    print(f"✅ 已更新 {INDEX_HTML}")
else:
    print("⚠️  没有解析到新闻条目")
