#!/usr/bin/env python3
"""
AI News to DayNews Website Publisher
将 AI 新闻推送到 daynews 网站
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# 路径配置
AI_NEWS_DIR = Path.home() / ".openclaw/workspace/skills/ai-news-zh/outputs"
DAYNEWS_DOCS = Path.home() / ".openclaw/workspace/daynews/docs"
AI_NEWS_PAGE = DAYNEWS_DOCS / "ai-news.html"
AI_NEWS_JSON = DAYNEWS_DOCS / "ai-news.json"

def get_latest_ai_news() -> List[Path]:
    """获取最新的 AI 新闻文件（今天的）"""
    today = datetime.now().strftime("%Y-%m-%d")
    files = list(AI_NEWS_DIR.glob(f"*{today}*.md"))
    return sorted(files, reverse=True)

def parse_ai_news_md(md_file: Path) -> Dict:
    """解析 AI 新闻 Markdown 文件"""
    content = md_file.read_text(encoding='utf-8')
    
    # 提取标题中的时间
    time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', content)
    timestamp = time_match.group(1) if time_match else datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 提取新闻条目
    items = []
    # 匹配格式：1️⃣ 💰🛡️ **标题** \n 摘要 \n 🔗 链接
    pattern = r'(\d+)️⃣\s+([^\*]+?)\*\*(.+?)\*\*\n(.+?)\n🔗\s+(.+?)(?=\n\n|\n\d+️⃣|$)'
    
    for match in re.finditer(pattern, content, re.DOTALL):
        num, tags, title, summary, link = match.groups()
        items.append({
            "number": num,
            "tags": tags.strip(),
            "title": title.strip(),
            "summary": summary.strip(),
            "link": link.strip()
        })
    
    return {
        "timestamp": timestamp,
        "count": len(items),
        "items": items,
        "raw_content": content
    }

def generate_html(news_data: List[Dict]) -> str:
    """生成 HTML 页面"""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 新闻 | DayNews</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .subtitle { opacity: 0.9; font-size: 1.1em; }
        .updates {
            padding: 20px 30px;
        }
        .update-section {
            margin-bottom: 40px;
            border-bottom: 1px solid #eee;
            padding-bottom: 30px;
        }
        .update-section:last-child { border-bottom: none; }
        .update-time {
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 15px;
        }
        .news-item {
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .news-number {
            display: inline-block;
            background: #667eea;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            text-align: center;
            line-height: 28px;
            font-weight: bold;
            margin-right: 10px;
        }
        .news-tags {
            display: inline-block;
            font-size: 1.2em;
            margin-right: 8px;
        }
        .news-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .news-summary {
            color: #555;
            margin-bottom: 10px;
            line-height: 1.7;
        }
        .news-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-size: 0.9em;
            margin-top: 8px;
        }
        .news-link:hover {
            text-decoration: underline;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 0.9em;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
        .back-link:hover {
            background: #5568d3;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI 新闻</h1>
            <div class="subtitle">实时追踪全球 AI 动态 · 每30分钟更新</div>
        </div>
        
        <div class="updates">
"""
    
    # 添加新闻内容
    for update in news_data[:10]:  # 最多显示最近10次更新
        html += f"""
            <div class="update-section">
                <div class="update-time">📅 {update['timestamp']} ({update['count']}条)</div>
"""
        for item in update['items']:
            html += f"""
                <div class="news-item">
                    <div>
                        <span class="news-number">{item['number']}</span>
                        <span class="news-tags">{item['tags']}</span>
                        <span class="news-title">{item['title']}</span>
                    </div>
                    <div class="news-summary">{item['summary']}</div>
                    <a href="{item['link']}" target="_blank" class="news-link">🔗 查看原文</a>
                </div>
"""
        html += """
            </div>
"""
    
    html += """
        </div>
        
        <div class="footer">
            <a href="index.html" class="back-link">← 返回财经早报</a>
            <div style="margin-top: 20px;">
                数据源：TechCrunch, VentureBeat, The Verge, Wired 等27+个源<br>
                更新频率：每30分钟 | 采集技能：ai-news-zh v2.0
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def update_index_add_ai_link():
    """在主页添加 AI 新闻入口"""
    index_file = DAYNEWS_DOCS / "index.html"
    
    if not index_file.exists():
        print("⚠️  index.html 不存在")
        return
    
    content = index_file.read_text(encoding='utf-8')
    
    # 检查是否已有 AI 新闻链接
    if "ai-news.html" in content:
        print("✅ 主页已有 AI 新闻链接")
        return
    
    # 在标题附近添加链接（需要根据实际HTML结构调整）
    ai_link = '<a href="ai-news.html" style="margin-left: 20px; color: #667eea;">🤖 AI新闻</a>'
    
    # 简单替换策略（实际可能需要更精确的DOM操作）
    content = content.replace(
        '<title>DayNews',
        f'{ai_link}\n    <title>DayNews'
    )
    
    index_file.write_text(content, encoding='utf-8')
    print("✅ 已在主页添加 AI 新闻入口")

def main():
    print("🚀 AI News to DayNews Publisher")
    print("=" * 50)
    
    # 获取最新 AI 新闻
    latest_files = get_latest_ai_news()
    
    if not latest_files:
        print("⚠️  今天没有 AI 新闻文件")
        return 1
    
    print(f"📰 找到 {len(latest_files)} 个 AI 新闻文件")
    
    # 解析所有新闻
    news_data = []
    for file in latest_files:
        try:
            data = parse_ai_news_md(file)
            news_data.append(data)
            print(f"✅ 解析: {file.name} ({data['count']}条)")
        except Exception as e:
            print(f"❌ 解析失败: {file.name} - {e}")
    
    if not news_data:
        print("⚠️  没有有效的新闻数据")
        return 1
    
    # 生成 HTML
    html = generate_html(news_data)
    AI_NEWS_PAGE.write_text(html, encoding='utf-8')
    print(f"✅ 生成 HTML: {AI_NEWS_PAGE}")
    
    # 保存 JSON（供其他工具使用）
    AI_NEWS_JSON.write_text(
        json.dumps(news_data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"✅ 生成 JSON: {AI_NEWS_JSON}")
    
    # 更新主页链接
    update_index_add_ai_link()
    
    print("\n✅ 发布完成！")
    print(f"🌐 访问: https://lijie999.github.io/daynews/ai-news.html")
    
    return 0

if __name__ == "__main__":
    exit(main())
