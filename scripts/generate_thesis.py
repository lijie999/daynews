#!/usr/bin/env python3
"""
生成主线结论：基于多个大站头条 + AI 智能分析
使用 web_search 工具（更可靠）
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

def main():
    print("🚀 Generating market thesis with AI analysis...", file=sys.stderr)
    
    # 构建 AI 任务：让 AI 自己搜索并分析
    task = """你是专业的金融市场分析师。请执行以下任务：

1. 使用 web_search 工具搜索今日（过去 24 小时）美股市场新闻头条，关键词：
   - "US stock market today"
   - "S&P 500 Nasdaq Dow Jones"  
   - "market news today"
   
   从 Yahoo Finance、CNBC、MarketWatch、Bloomberg 等主流媒体获取 10-15 条头条新闻。

2. 基于搜索到的头条新闻，生成简洁、专业的市场主线结论（150-200字）。

要求格式（Markdown，不要代码块）：
**市场走势**：指数/板块表现（1-2句，基于头条推断大方向，不虚构具体涨跌幅）

**核心驱动**：
• 驱动因子1（简洁描述）
• 驱动因子2
• 驱动因子3

**风险提示**：前瞻/风险点（1句）

注意：
1. 先调用 web_search 搜索新闻
2. 分析头条内容，提取市场主线
3. 不要虚构具体数据
4. 聚焦宏观驱动和板块主线
5. 语言简洁、信息密度高

直接输出最终的主线结论内容，不要解释搜索过程。"""

    # 加载内部 RSS 数据作为补充上下文
    internal_context = ""
    briefs_path = Path("/Users/lijiaolong/.openclaw/workspace/daynews/docs/briefs.json")
    if briefs_path.exists():
        try:
            briefs = json.loads(briefs_path.read_text(encoding="utf-8"))
            sections = briefs.get("sections", [])
            
            key_news = []
            for sec in sections:
                name = sec.get("name", "")
                if name in ["美联储与政策", "地缘/能源/避险", "七姐妹与半导体链"]:
                    items = sec.get("items", [])[:3]
                    for it in items:
                        title = it.get("title", "")
                        if title:
                            key_news.append(f"- {title[:80]} ({name})")
            
            if key_news:
                internal_context = "\n\n【可选参考：内部RSS数据】\n" + "\n".join(key_news[:10])
        except Exception:
            pass
    
    if internal_context:
        task += internal_context
    
    # 调用 openclaw agent（让 AI 自己搜索并分析）
    import subprocess
    try:
        print("📊 Calling AI agent for analysis...", file=sys.stderr)
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--session-id", "daynews-thesis-gen",
                "--message", task,
                "--timeout", "60"
            ],
            capture_output=True,
            text=True,
            timeout=65
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            
            # 移除可能的 markdown 代码块标记
            output = output.replace("```markdown", "").replace("```", "").strip()
            
            # 验证输出格式
            if "**市场走势**" in output and "**核心驱动**" in output:
                print(output)  # 输出到 stdout
                print("\n✅ Thesis generated successfully", file=sys.stderr)
                return 0
            else:
                print(f"❌ Invalid format: {output[:200]}", file=sys.stderr)
                raise ValueError("Invalid output format")
        else:
            print(f"❌ AI call failed: {result.stderr}", file=sys.stderr)
            raise RuntimeError("AI call failed")
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        # Fallback: 使用简单模板
        print("**市场走势**：美股震荡，关注科技股表现<br><br>**核心驱动**：<br>• Fed 政策预期持稳<br>• 科技板块结构分化<br>• 地缘与能源风险抬头<br><br>**风险提示**：短期波动率维持高位")
        return 1


if __name__ == "__main__":
    sys.exit(main())
