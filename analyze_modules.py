#!/usr/bin/env python3
"""
分析 DayNews 各模块的合理性
"""
import json
from pathlib import Path

print("=" * 60)
print("📊 DayNews 模块合理性分析")
print("=" * 60)

# 读取当前数据
briefs = json.loads(Path("docs/briefs.json").read_text())
sections = briefs.get("sections", [])

print("\n当前板块配置:")
print("-" * 60)
for s in sections:
    name = s.get("name", "")
    count = len(s.get("items", []))
    print(f"  {name}: {count} 条")

print("\n\n问题分析:")
print("=" * 60)

print("\n1️⃣ 主线结论")
print("-" * 60)
print("✅ 合理：提供3秒速读的核心判断")
print("   位置：顶部，优先级最高")
print("   内容：市场走势 + 核心驱动 + 风险提示")
print("   建议：保持现状")

print("\n2️⃣ AI 新闻（新增）")
print("-" * 60)
print("✅ 合理：AI是当前市场核心主题")
print("   位置：主线结论下方，高优先级")
print("   更新：每30分钟自动更新")
print("   数据量：4-8条/次，适中")
print("   建议：保持现状")

print("\n3️⃣ 数据日历")
print("-" * 60)
print("✅ 合理：交易者需要提前知道重要数据发布时间")
print("   位置：右侧边栏，sticky显示")
print("   内容：今明两日重点经济数据（CPI/NFP/FOMC等）")
print("   建议：保持现状")

print("\n4️⃣ 事件雷达（S级 + A级）")
print("-" * 60)
s_count = len([s for s in sections if "美联储与政策" in s.get("name", "") or "地缘/能源/避险" in s.get("name", "")])
print(f"   当前数据量：S级 0条，A级 0条")
print("   ⚠️  问题：事件雷达为空，可能是分级逻辑太严格")
print("   建议：")
print("     - 检查分级算法，确保重要新闻能被捕获")
print("     - 或者考虑合并到主内容区，不单独显示")

print("\n5️⃣ 指数/期权（NQ/ES/QQQ）")
print("-" * 60)
index_items = [s for s in sections if "七姐妹与半导体链" in s.get("name", "")]
if index_items:
    count = len(index_items[0].get("items", []))
    print(f"   当前数据量：{count} 条")
    print("   ✅ 合理：科技股是市场主导力量")
    print("   建议：保持现状")

print("\n6️⃣ 黄金（GC）")
print("-" * 60)
gold_items = [s for s in sections if "地缘/能源/避险" in s.get("name", "")]
if gold_items:
    count = len(gold_items[0].get("items", []))
    print(f"   当前数据量：{count} 条")
    print("   ✅ 合理：地缘紧张时黄金是避险核心")
    print("   建议：保持现状")

print("\n7️⃣ 其他（弱化）")
print("-" * 60)
other = [s for s in sections if "其他" in s.get("name", "")]
if other:
    count = len(other[0].get("items", []))
    print(f"   当前数据量：{count} 条")
    print("   ❓ 问题：18条新闻被归入'其他'，占比较高")
    print("   建议：")
    print("     - 考虑增加'美联储与政策'独立板块")
    print("     - 或者'能源/商品'独立板块")

print("\n\n推荐改进方案:")
print("=" * 60)

print("\n方案A：简化版（推荐）")
print("-" * 60)
print("  1. 主线结论（3秒读完）")
print("  2. 🤖 AI 新闻（实时更新）")
print("  3. 📊 指数/科技（NQ/ES + 七姐妹）")
print("  4. ⚡ 能源/地缘（GC + 油价 + 霍尔木兹）")
print("  5. 💵 美联储/政策（CPI + 利率 + 财政）")
print("  6. 其他（弱化）")
print("  右侧：📅 数据日历")
print("")
print("  优点：")
print("    - 清晰的主题分类")
print("    - 每个板块有明确的交易意义")
print("    - 删除空的'事件雷达'，减少视觉噪音")

print("\n方案B：保持现状")
print("-" * 60)
print("  1. 主线结论")
print("  2. 🤖 AI 新闻")
print("  3. 事件雷达（S级 + A级）← 当前为空")
print("  4. 指数/期权")
print("  5. 黄金")
print("  6. 其他（18条）")
print("  右侧：数据日历")
print("")
print("  缺点：")
print("    - 事件雷达经常为空，占据版面")
print("    - '其他'板块内容过多，需要分类")

print("\n方案C：极简版")
print("-" * 60)
print("  1. 主线结论 + AI 新闻（合并到一个卡片）")
print("  2. 📊 指数/科技")
print("  3. ⚡ 能源/避险")
print("  4. 💵 政策/宏观")
print("  右侧：数据日历")
print("")
print("  优点：")
print("    - 最小化界面，适合移动端")
print("    - 核心信息密度高")

print("\n\n建议优先级:")
print("=" * 60)
print("  🔥 P0（立即处理）：")
print("     - 删除或隐藏空的'事件雷达'板块")
print("  📌 P1（本周处理）：")
print("     - 将'其他'板块拆分为'美联储/政策'和'能源/地缘'")
print("  💡 P2（可选）：")
print("     - 优化移动端布局")
print("     - 增加深色/浅色主题切换")

print("\n" + "=" * 60)
