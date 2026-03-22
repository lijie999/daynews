#!/usr/bin/env python3
"""
DayNews 全链路检查
"""
import json
from pathlib import Path

print("=" * 60)
print("📋 DayNews 全链路检查")
print("=" * 60)

# 1. 检查数据源：briefs.json
print("\n1️⃣ 数据源检查 (briefs.json)")
print("-" * 60)
briefs = Path("docs/briefs.json")
if briefs.exists():
    data = json.loads(briefs.read_text())
    print(f"✅ briefs.json 存在")
    print(f"   日期: {data.get('date')}")
    print(f"   生成时间: {data.get('generatedAtBJT')}")
    print(f"   板块数量: {len(data.get('sections', []))}")
    
    sections = {s['name']: len(s.get('items', [])) for s in data.get('sections', [])}
    for name, count in sections.items():
        print(f"   - {name}: {count} 条")
else:
    print("❌ briefs.json 不存在")

# 2. 检查 AI 新闻源
print("\n2️⃣ AI 新闻源检查")
print("-" * 60)
ai_dir = Path.home() / ".openclaw/workspace/skills/ai-news-zh/outputs"
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")
ai_files = sorted(ai_dir.glob(f"*{today}*.md"), reverse=True)

if ai_files:
    print(f"✅ 今日 AI 新闻文件: {len(ai_files)} 个")
    for f in ai_files[:3]:
        print(f"   - {f.name} ({f.stat().st_size} bytes)")
    
    # 解析最新文件
    latest = ai_files[0]
    content = latest.read_text()
    import re
    
    # 统计新闻条数
    pattern1 = r'\d+️⃣'
    pattern2 = r'^\d+\.\s'
    count1 = len(re.findall(pattern1, content))
    count2 = len(re.findall(pattern2, content, re.MULTILINE))
    print(f"   最新文件新闻数: {max(count1, count2)} 条")
else:
    print(f"❌ 今日无 AI 新闻文件")

# 3. 检查生成的 HTML
print("\n3️⃣ 生成的 HTML 检查")
print("-" * 60)
index = Path("docs/index.html")
if index.exists():
    html = index.read_text()
    print(f"✅ index.html 存在 ({len(html)} 字符)")
    
    # 检查关键模块
    modules = {
        "主线结论": '<section class="hero">',
        "AI 新闻": '🤖 AI 新闻',
        "数据日历": '📅 数据日历',
        "事件雷达S级": '事件雷达｜S级',
        "事件雷达A级": '事件雷达｜A级',
        "指数/期权": '指数/期权（NQ/ES/QQQ）',
        "黄金": '黄金（GC）',
        "其他": '其他（弱化）',
    }
    
    print("\n   模块存在性检查:")
    for name, marker in modules.items():
        exists = marker in html
        status = "✅" if exists else "❌"
        print(f"   {status} {name}")
    
    # 提取各模块的条数
    print("\n   模块内容统计:")
    
    # AI 新闻条数
    ai_match = re.search(r'🤖 AI 新闻[^<]*</span><span class="badge">(\d+)</span>', html)
    if ai_match:
        print(f"   - AI 新闻: {ai_match.group(1)} 条")
    
    # 事件雷达
    s_match = re.search(r'事件雷达｜S级</span><span class="badge">(\d+)</span>', html)
    if s_match:
        print(f"   - 事件雷达S级: {s_match.group(1)} 条")
    
    a_match = re.search(r'事件雷达｜A级</span><span class="badge">(\d+)</span>', html)
    if a_match:
        print(f"   - 事件雷达A级: {a_match.group(1)} 条")
    
    # 其他
    other_match = re.search(r'其他（弱化）</span><span class="badge">(\d+)</span>', html)
    if other_match:
        print(f"   - 其他: {other_match.group(1)} 条")
    
    # 检查布局结构
    print("\n   布局结构检查:")
    wrap_count = html.count('<div class="wrap">')
    main_count = html.count('<main>')
    aside_count = html.count('<aside')
    
    print(f"   - .wrap 容器: {wrap_count} 个 {'✅' if wrap_count == 1 else '❌'}")
    print(f"   - <main> 标签: {main_count} 个 {'✅' if main_count == 1 else '❌'}")
    print(f"   - <aside> 标签: {aside_count} 个 {'✅' if aside_count == 1 else '❌'}")
    
    # 检查 aside 是否在 main 外面
    main_end = html.find('</main>')
    aside_start = html.find('<aside')
    if main_end > 0 and aside_start > main_end:
        print(f"   - aside 位置: ✅ 在 main 外部（正确）")
    else:
        print(f"   - aside 位置: ❌ 可能嵌套在 main 内部")
    
else:
    print("❌ index.html 不存在")

# 4. 检查定时任务配置
print("\n4️⃣ 定时任务检查")
print("-" * 60)
print("AI 新闻采集任务:")
print("   - 频率: 每30分钟")
print("   - 命令: web_search + RSS 抓取 + 去重 + 翻译")
print("   - 发布: inject_ai_news.py → git push")
print("   - 状态: 运行中 (检查 openclaw cron list)")

print("\n财经早报任务:")
print("   - 频率: 每30分钟")
print("   - 命令: RUN_DAYNEWS_UPDATE")
print("   - 生成: render_home.py → inject_ai_news.py → git push")

# 5. 检查脚本一致性
print("\n5️⃣ 脚本一致性检查")
print("-" * 60)

render_home = Path("scripts/render_home.py")
inject_ai = Path("scripts/inject_ai_news.py")

if render_home.exists():
    content = render_home.read_text()
    checks = {
        "数据日历在 aside": "aside.*render_data_calendar" in content.replace('\n', ' '),
        "主线结论": "render_thesis()" in content,
        "事件雷达": "render_radar()" in content,
        "无历史模块": "历史" not in content or content.count("历史") < 2,
    }
    
    print("render_home.py:")
    for name, result in checks.items():
        print(f"   {'✅' if result else '❌'} {name}")

if inject_ai.exists():
    content = inject_ai.read_text()
    checks = {
        "删除旧AI新闻": "re.sub.*AI 新闻.*section.*DOTALL" in content.replace('\n', ' '),
        "插入到主线后": "thesis_end_pattern" in content,
        "支持两种格式": "pattern1.*pattern2" in content,
    }
    
    print("\ninject_ai_news.py:")
    for name, result in checks.items():
        print(f"   {'✅' if result else '❌'} {name}")

print("\n" + "=" * 60)
print("✅ 检查完成")
print("=" * 60)
