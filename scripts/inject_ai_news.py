#!/usr/bin/env python3
"""AI News Injection with Carousel - supports all formats"""
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

# 通用解析器 - 支持最新格式
matches = list(re.finditer(
    r'###\s+(.+?)\n\*\*(.+?)\*\*\n-\s+🔗\s+来源：\[(.+?)\]\((.+?)\)\n-\s+📅\s+时间：(.+?)\n\n(.+?)(?:\n\n\*\*标签\*\*：(.+?))?(?=\n\n---|\n\n###|\n\n##|\Z)',
    content, re.DOTALL
))

for idx, m in enumerate(matches):
    title, keywords, source, link, time, summary, tags = m.groups()
    combined = ((tags or "") + " " + keywords + " " + summary).lower()
    
    # 智能分类
    emoji = "🤖"
    badge_type = "rB"
    badge_text = "AI"
    
    if "融资" in combined or "funding" in combined or "投资" in combined:
        emoji = "💰"
        badge_type = "rA"
        badge_text = "融资"
    elif "模型" in combined or "model" in combined or "gpt" in combined or "memory" in combined or "compression" in combined:
        emoji = "🧠"
        badge_type = "rA"
        badge_text = "模型"
    elif "监管" in combined or "政策" in combined or "regulation" in combined or "policy" in combined:
        emoji = "🛡️"
        badge_type = "rS"
        badge_text = "监管"
    elif "agent" in combined or "代理" in combined:
        emoji = "🤖"
        badge_type = "rA"
        badge_text = "Agent"
    elif "应用" in combined or "product" in combined:
        emoji = "🔧"
        badge_type = "rB"
        badge_text = "应用"
    
    items.append({
        "title": title.strip(),
        "summary": summary.strip()[:200] + ("..." if len(summary.strip()) > 200 else ""),
        "link": link.strip(),
        "emoji": emoji,
        "badge_type": badge_type,
        "badge_text": badge_text
    })
    if len(items) >= 16:  # 支持4页轮播，每页4条
        break

print(f"✅ 解析到 {len(items)} 条新闻")

if not items:
    print("⚠️  没有解析到新闻条目")
    exit(0)

# 生成轮播 HTML
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

# 分页生成
for page_idx in range(total_pages):
    start_idx = page_idx * items_per_page
    end_idx = min(start_idx + items_per_page, len(items))
    page_items = items[start_idx:end_idx]
    
    active_class = ' active' if page_idx == 0 else ''
    html += f'    <div class="ai-carousel-page{active_class}" data-page="{page_idx}">\n'
    html += '      <div class="tlist">\n'
    
    for it in page_items:
        html += f'''        <div class="titem">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start">
            <div class="rbadge {it["badge_type"]}" style="font-size:10px;padding:6px 10px;height:auto;border-radius:8px">{it["badge_text"]}</div>
            <div>
              <a class="ttitle" href="{it['link']}" target="_blank" rel="noreferrer noopener">{it['title']}</a>
              <div style="margin-top:8px;color:var(--muted);font-size:14px;line-height:1.5">{it['summary']}</div>
            </div>
          </div>
        </div>
'''
    
    html += '      </div>\n'
    html += '    </div>\n'

html += '''  </div>
  <button class="carousel-btn carousel-next" onclick="aiNewsCarousel.next()">›</button>
</div>
<div class="carousel-dots">
'''

# 分页指示器
for i in range(total_pages):
    active_class = ' active' if i == 0 else ''
    html += f'  <span class="carousel-dot{active_class}" data-page="{i}" onclick="aiNewsCarousel.goTo({i})"></span>\n'

html += f'''</div>
<script>
const aiNewsCarousel = {{
  currentPage: 0,
  totalPages: {total_pages},
  
  goTo(page) {{
    if (page < 0 || page >= this.totalPages) return;
    
    document.querySelectorAll('.ai-carousel-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.carousel-dot').forEach(d => d.classList.remove('active'));
    
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
</section>
'''

# 读取并更新 index.html
page_content = INDEX_HTML.read_text(encoding='utf-8')

# 删除所有现有 AI 新闻板块
page_content = re.sub(
    r'<section class="card[^"]*"[^>]*>\s*<h2[^>]*>\s*<span>🤖 AI 新闻.*?</section>\s*',
    '',
    page_content,
    flags=re.DOTALL
)

# 插入新的轮播板块
page_content = re.sub(
    r'(</section>)(\s*<div class="grid3">)',
    f'\\1\n\n      {html}\n\\2',
    page_content,
    count=1
)

INDEX_HTML.write_text(page_content, encoding='utf-8')
print(f"✅ 已更新 {INDEX_HTML}，共 {total_pages} 页，每页 {items_per_page} 条新闻")
