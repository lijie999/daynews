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
    """获取最新 AI 新闻条���"""
    # 获取最新的文件（不限日期）
    files = sorted(AI_NEWS_DIR.glob("*.md"), reverse=True, key=lambda p: p.stat().st_mtime)
    
    if not files:
        return []
    
    # 读取最新文件
    latest_file = files[0]
    content = latest_file.read_text(encoding='utf-8')
    
    # 提取新闻条目
    items = []
    
    # 最新格式（2026-03-26 13:02 S/A/B级格式）:
    # ### 🚀 标题
    # - **来源**: Source | Author
    # - **时间**: ...
    # - **链接**: URL
    # - **简介**: 摘要
    pattern_sab = r'###\s+([🚀💼🔬🧠💰🛒🌐🤖📊🏛️🐄]+)\s+(.+?)\n-\s+\*\*来源\*\*:\s+(.+?)\n-\s+\*\*时间\*\*:\s+(.+?)\n-\s+\*\*链接\*\*:\s+(.+?)\n-\s+\*\*简介\*\*:\s+(.+?)(?=\n\n###|\n\n##|\Z)'
    matches = list(re.finditer(pattern_sab, content, re.DOTALL))
    
    if matches:
        for idx, match in enumerate(matches):
            emoji, title, source, pub_time, link, summary = match.groups()
            
            # 根据 emoji 分类
            tag_emojis = emoji.strip()
            
            items.append({
                "number": str(idx + 1),
                "tags": tag_emojis,
                "title": title.strip(),
                "summary": summary.strip()[:200] + "..." if len(summary.strip()) > 200 else summary.strip(),
                "link": link.strip()
            })
            
            if len(items) >= limit:
                break
    
    # 次新格式（2026-03-26 02:01）:
    # ### 序号. 标题
    # **标签**: #标签1 #标签2
    # **时间**: ...
    # **来源**: Source
    # **原文**: URL
    # 
    # 摘要内容
    if not items:
        pattern_new = r'###\s+\d+\.\s+(.+?)\n\*\*标签\*\*:\s+(.+?)\n\*\*时间\*\*:.+?\n\*\*来源\*\*:\s+(.+?)\n\*\*原文\*\*:\s+(.+?)\n\n(.+?)(?=\n\n---|\n\n###|\n\n##|\Z)'
        matches = list(re.finditer(pattern_new, content, re.DOTALL))
        
        if matches:
            for idx, match in enumerate(matches):
                title, tags, source, link, summary = match.groups()
                
                # 从标签中提取 emoji
                tag_emojis = "🤖"
                if any(x in tags for x in ["融资", "收购", "投资"]):
                    tag_emojis = "💰"
                elif any(x in tags for x in ["监管", "禁令", "政策", "争议"]):
                    tag_emojis = "🛡️"
                elif any(x in tags for x in ["大模型", "模型", "GPT"]):
                    tag_emojis = "🧠"
                elif "Agent" in tags or "代理" in tags:
                    tag_emojis = "🤖"
                elif any(x in tags for x in ["应用", "产品"]):
                    tag_emojis = "🔧"
                
                items.append({
                    "number": str(idx + 1),
                    "tags": tag_emojis,
                    "title": title.strip(),
                    "summary": summary.strip()[:200] + "..." if len(summary.strip()) > 200 else summary.strip(),
                    "link": link.strip()
                })
                
                if len(items) >= limit:
                    break
    
    # 格式2（2026-03-25旧版）:
    # **序号. emoji 标题**
    # 🏷️ `标签1` `标签2`
    # 摘要内容
    # 🔗 [来源](URL) | 日期
    if not items:
        pattern_latest = r'\*\*\d+\.\s+((?:🚀|💰|🛡️|🧠|🤖|⚡|🔧|📱|🐄|🇨🇳|📊|🔴|🏦|🔒|🏛️|💳)?)\s*(.+?)\*\*\s*\n🏷️\s+(.+?)\n(.+?)\n🔗\s+\[(.+?)\]\((.+?)\)\s+\|\s+(.+?)(?=\n\n\*\*\d+\.|\n\n---|\n\n##|\Z)'
        matches = list(re.finditer(pattern_latest, content, re.DOTALL))
        
        if matches:
            for idx, match in enumerate(matches):
                emoji, title, tags, summary, source, link, pub_date = match.groups()
                
                # 从标签中提取 emoji（如果没有emoji前缀）
                if not emoji:
                    if "融资" in tags or "收购" in tags:
                        emoji = "💰"
                    elif "监管" in tags or "禁令" in tags or "争议" in tags or "安全" in tags:
                        emoji = "🛡️"
                    elif "大模型" in tags or "模型" in tags:
                        emoji = "🧠"
                    elif "Agent" in tags:
                        emoji = "🤖"
                    else:
                        emoji = "🤖"
                
                items.append({
                    "number": str(idx + 1),
                    "tags": emoji,
                    "title": title.strip(),
                    "summary": summary.strip()[:200] + "..." if len(summary.strip()) > 200 else summary.strip(),
                    "link": link.strip()
                })
                
                if len(items) >= limit:
                    break
    
    # 如果以上格式都没匹配到，尝试更早的格式...
    if not items:
        # 格式2（2026-03-24 新版本）:
        # ### 标题
        # **来源**: Source | **发布时间**: Time
        # 内容...
        # **标签**: `tag1` `tag2`
        # **原文**: URL
        pattern_current = r'###\s+(.+?)\n\*\*来源\*\*:\s+(.+?)\s+\|\s+\*\*发布时间\*\*:\s+(.+?)\n\n(.+?)\n\n\*\*标签\*\*:\s+(.+?)\n\*\*原文\*\*:\s+(.+?)(?=\n\n---|\n\n###|\n\n##|\Z)'
        matches = list(re.finditer(pattern_current, content, re.DOTALL))
        
        if matches:
            for idx, match in enumerate(matches):
                title, source, pub_time, summary, tags, link = match.groups()
                
                # 从标签中提取 emoji
                tag_emojis = "🤖"
                if "融资" in tags or "收购" in tags:
                    tag_emojis = "💰"
                elif "监管" in tags or "禁令" in tags or "争议" in tags:
                    tag_emojis = "🛡️"
                elif "大模型" in tags or "模型" in tags:
                    tag_emojis = "🧠"
                
                items.append({
                    "number": str(idx + 1),
                    "tags": tag_emojis,
                    "title": title.strip(),
                    "summary": summary.strip()[:200] + "..." if len(summary.strip()) > 200 else summary.strip(),
                    "link": link.strip()
                })
                
                if len(items) >= limit:
                    break
    
    # 格式3（更早的格式）
    if not items:
        # 尝试之前的格式: ### emoji 标题 \n **分类**: ... | **来源**: ...
        pattern_prev = r'###\s+(?:🚀|💰|🛡️|🧠|🤖|⚡|🔧|📱|🐄|🇨🇳|📊)?\s*(.+?)\n\*\*分类\*\*:\s+(.+?)\s+\|\s+\*\*来源\*\*:\s+(.+?)\n(.+?)- \*\*链接\*\*:\s+(.+?)(?=\n\n###|\n\n##|\Z)'
        matches = list(re.finditer(pattern_prev, content, re.DOTALL))
        
        if matches:
            for idx, match in enumerate(matches):
                title, category, source, summary_block, link = match.groups()
                
                # 从摘要块中提取第一行
                summary_lines = [line.strip('- ').strip() for line in summary_block.split('\n') if line.strip().startswith('- ') and '链接' not in line]
                summary = summary_lines[0] if summary_lines else title
                
                # 从分类中提取 emoji
                tag_emojis = "🤖"
                if "融资" in category or "收购" in category:
                    tag_emojis = "💰"
                elif "监管" in category or "禁令" in category or "争议" in category:
                    tag_emojis = "🛡️"
                elif "大模型" in category or "模型" in category or "技术" in category:
                    tag_emojis = "🧠"
                
                items.append({
                    "number": str(idx + 1),
                    "tags": tag_emojis,
                    "title": title.strip(),
                    "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                    "link": link.strip()
                })
                
                if len(items) >= limit:
                    break
    
    return items

def generate_ai_news_section_html(items):
    """生成 AI 新闻板块 HTML（带翻页轮播）"""
    if not items:
        return '<section class="card"><h2><span>🤖 AI 新闻</span><span class="badge">0</span></h2><div class="tlist"><div class="note">（今日暂无 AI 新闻）</div></div></section>'
    
    # 每页显示4条新闻
    items_per_page = 4
    total_pages = (len(items) + items_per_page - 1) // items_per_page
    
    html = f'''<section class="card ai-news-carousel">
<h2>
  <span>🤖 AI 新闻（每30分钟更新）</span>
  <span class="badge">{len(items)}</span>
</h2>
<div class="ai-carousel-wrapper">
  <button class="carousel-btn carousel-prev" onclick="aiNewsCarousel.prev()">‹</button>
  <div class="ai-carousel-container">
'''
    
    # 分页生成新闻
    for page_idx in range(total_pages):
        start_idx = page_idx * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        page_items = items[start_idx:end_idx]
        
        active_class = ' active' if page_idx == 0 else ''
        html += f'    <div class="ai-carousel-page{active_class}" data-page="{page_idx}">\n'
        html += '      <div class="tlist">\n'
        
        for item in page_items:
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
            
            html += f'''        <div class="titem">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start">
            <div class="rbadge {badge_class}" style="font-size:10px;padding:6px 10px;height:auto;border-radius:8px">{badge_text}</div>
            <div>
              <a class="ttitle" href="{item['link']}" target="_blank" rel="noreferrer noopener">{item['title']}</a>
              <div style="margin-top:8px;color:var(--muted);font-size:14px;line-height:1.5">{item['summary']}</div>
            </div>
          </div>
        </div>
'''
        
        html += '      </div>\n'
        html += '    </div>\n'
    
    html += f'''  </div>
  <button class="carousel-btn carousel-next" onclick="aiNewsCarousel.next()">›</button>
</div>
<div class="carousel-dots">
'''
    
    # 生成分页指示器
    for i in range(total_pages):
        active_class = ' active' if i == 0 else ''
        html += f'  <span class="carousel-dot{active_class}" data-page="{i}" onclick="aiNewsCarousel.goTo({i})"></span>\n'
    
    html += f'''</div>
<script>
// AI 新闻轮播控制
const aiNewsCarousel = {{
  currentPage: 0,
  totalPages: {total_pages},
  
  goTo(page) {{
    if (page < 0 || page >= this.totalPages) return;
    
    // 隐藏当前页
    document.querySelectorAll('.ai-carousel-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.carousel-dot').forEach(d => d.classList.remove('active'));
    
    // 显示目标页
    document.querySelector(`.ai-carousel-page[data-page="${{page}}"]`).classList.add('active');
    document.querySelector(`.carousel-dot[data-page="${{page}}"]`).classList.add('active');
    
    this.currentPage = page;
  }},
  
  next() {{
    this.goTo((this.currentPage + 1) % this.totalPages);
  }},
  
  prev() {{
    this.goTo((this.currentPage - 1 + this.totalPages) % this.totalPages);
  }}
}};

// 键盘快捷键
document.addEventListener('keydown', (e) => {{
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') aiNewsCarousel.prev();
  if (e.key === 'ArrowRight') aiNewsCarousel.next();
}});
</script>
<style>
.ai-news-carousel {{
  position: relative;
}}

.ai-carousel-wrapper {{
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
}}

.ai-carousel-container {{
  flex: 1;
  overflow: hidden;
  position: relative;
}}

.ai-carousel-page {{
  display: none;
}}

.ai-carousel-page.active {{
  display: block;
}}

.carousel-btn {{
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: var(--text);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 24px;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}}

.carousel-btn:hover {{
  background: rgba(255,255,255,0.15);
  border-color: rgba(255,255,255,0.3);
  transform: scale(1.05);
}}

.carousel-btn:active {{
  transform: scale(0.95);
}}

.carousel-dots {{
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 12px 0 8px;
}}

.carousel-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  cursor: pointer;
  transition: all 0.2s;
}}

.carousel-dot:hover {{
  background: rgba(255,255,255,0.4);
  transform: scale(1.2);
}}

.carousel-dot.active {{
  background: rgba(255,176,32,0.8);
  width: 24px;
  border-radius: 4px;
}}
</style>
</section>'''
    
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
    
    # 获取 AI 新闻（增加到12条，支持3页翻页）
    ai_items = get_latest_ai_news_items(limit=12)
    ai_section_html = generate_ai_news_section_html(ai_items)
    
    # 查找主线结论后、grid3 之前的位置
    # 匹配模式：</section>（主线结论结束） + 任意空白 + <div class="grid3">
    insertion_pattern = r'(</section>)(\s*<div class="grid3">)'
    
    if not re.search(insertion_pattern, content):
        print("❌ 找不到插入位置（主线结论与grid3之间）")
        return False
    
    # 在主线结论后、grid3前插入 AI 新闻
    new_content = re.sub(
        insertion_pattern,
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
