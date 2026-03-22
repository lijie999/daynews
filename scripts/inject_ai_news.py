#!/usr/bin/env python3
"""
Inject AI News section into DayNews index.html
在 DayNews 主页插入 AI 新闻板块
"""

import json
import re
from pathlib import Path
from datetime import datetime

DAYNEWS_DOCS = Path.home() / ".openclaw/workspace/daynews/docs"
INDEX_HTML = DAYNEWS_DOCS / "index.html"
AI_NEWS_DIR = Path.home() / ".openclaw/workspace/skills/ai-news-zh/outputs"

def get_latest_ai_news_items(limit=10):
    """获取最新 AI 新闻条目"""
    today = datetime.now().strftime("%Y-%m-%d")
    files = sorted(AI_NEWS_DIR.glob(f"*{today}*.md"), reverse=True)
    
    if not files:
        return []
    
    # 读取最新文件
    latest_file = files[0]
    content = latest_file.read_text(encoding='utf-8')
    
    # 提取新闻条目
    items = []
    # 支持两种格式：
    # 格式1: 1️⃣ 💰🛡️ **标题** \n 摘要 \n 🔗 链接
    # 格式2: 1. 🤖Agent **标题** \n 摘要 \n 🔗 链接
    
    # 尝试格式1（带emoji数字）
    pattern1 = r'(\d+)️⃣\s+([^\*]+?)\*\*(.+?)\*\*\n(.+?)\n🔗\s+(.+?)(?=\n\n|\n\d+️⃣|$)'
    matches = list(re.finditer(pattern1, content, re.DOTALL))
    
    if not matches:
        # 尝试格式2（普通数字）
        pattern2 = r'(\d+)\.\s+([^\*]+?)\*\*(.+?)\*\*\n\s*(.+?)\n\s*🔗\s+(.+?)(?=\n\n|\n\d+\.|---|\Z)'
        matches = list(re.finditer(pattern2, content, re.DOTALL))
    
    for match in matches:
        num, tags, title, summary, link = match.groups()
        items.append({
            "number": num,
            "tags": tags.strip(),
            "title": title.strip(),
            "summary": summary.strip()[:200] + "..." if len(summary.strip()) > 200 else summary.strip(),
            "link": link.strip()
        })
        
        if len(items) >= limit:
            break
    
    return items

def generate_ai_news_section_html(items):
    """生成 AI 新闻板块 HTML"""
    if not items:
        return '<section class="card"><h2><span>🤖 AI 新闻</span><span class="badge">0</span></h2><div class="tlist"><div class="note">（今日暂无 AI 新闻）</div></div></section>'
    
    html = f'<section class="card"><h2><span>🤖 AI 新闻（每30分钟更新）</span><span class="badge">{len(items)}</span></h2><div class="tlist">'
    
    for item in items:
        # 映射 emoji 到 badge 类型
        if "💰" in item["tags"]:
            badge_class = "rA"
            badge_text = "融资"
        elif "🛡️" in item["tags"]:
            badge_class = "rS"
            badge_text = "监管"
        elif "🧠" in item["tags"]:
            badge_class = "rA"
            badge_text = "模型"
        elif "🤖" in item["tags"]:
            badge_class = "rA"
            badge_text = "Agent"
        elif "🔧" in item["tags"]:
            badge_class = "rB"
            badge_text = "应用"
        else:
            badge_class = "rB"
            badge_text = "其他"
        
        html += f'''
<div class="titem">
  <div style="display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start">
    <div class="rbadge {badge_class}" style="font-size:10px;padding:6px 10px;height:auto;border-radius:8px">{badge_text}</div>
    <div>
      <a class="ttitle" href="{item['link']}" target="_blank" rel="noreferrer noopener">{item['title']}</a>
      <div style="margin-top:8px;color:var(--muted);font-size:14px;line-height:1.5">{item['summary']}</div>
    </div>
  </div>
</div>
'''
    
    html += '</div></section>'
    return html

def inject_ai_news_to_index():
    """将 AI 新闻注入到 index.html"""
    if not INDEX_HTML.exists():
        print(f"❌ {INDEX_HTML} 不存在")
        return False
    
    # 读取当前 HTML
    content = INDEX_HTML.read_text(encoding='utf-8')
    
    # 先删除所有现有的 AI 新闻板块（避免重复）
    # 匹配模式：<section class="card"><h2><span>🤖 AI 新闻...整个section
    ai_section_pattern = r'<section class="card"><h2><span>🤖 AI 新闻[^<]*</span>.*?</section>\n*'
    content = re.sub(ai_section_pattern, '', content, flags=re.DOTALL)
    
    # 获取 AI 新闻
    ai_items = get_latest_ai_news_items(limit=8)
    ai_section_html = generate_ai_news_section_html(ai_items)
    
    # 查找"数据日历"板块的位置（在主线结论之后）
    # 匹配模式：主线结论的 </section> 后面
    thesis_end_pattern = r'(</div>\s*</section>)(\s*<section class="card)'
    
    if not re.search(thesis_end_pattern, content):
        print("❌ 找不到主线结论板块")
        return False
    
    # 在主线结论后插入 AI 新闻
    new_content = re.sub(
        thesis_end_pattern,
        f'\\1\n\n      {ai_section_html}\\2',
        content,
        count=1  # 只替换第一个匹配
    )
    
    # 写回文件
    INDEX_HTML.write_text(new_content, encoding='utf-8')
    
    print(f"✅ 已注入 {len(ai_items)} 条 AI 新闻到 {INDEX_HTML}")
    return True

def main():
    print("🚀 Inject AI News to DayNews Index")
    print("=" * 50)
    
    if inject_ai_news_to_index():
        print("✅ 注入成功！")
        return 0
    else:
        print("❌ 注入失败")
        return 1

if __name__ == "__main__":
    exit(main())
