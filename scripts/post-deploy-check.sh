#!/usr/bin/env bash
# DayNews 发布后检查脚本
# 用途：每次 git push 后自动验证部署状态

set -e

SITE_URL="https://lijie999.github.io/daynews/"
REPO_DIR="$HOME/.openclaw/workspace/daynews"

echo "🔍 DayNews 发布检查"
echo "===================="
echo ""

# 1. 检查本地提交状态
echo "📦 1. 检查本地 Git 状态..."
cd "$REPO_DIR"
if git status --porcelain | grep -q .; then
  echo "⚠️  警告：有未提交的本地更改"
  git status --short
else
  echo "✅ 本地仓库干净"
fi
echo ""

# 2. 检查最新提交
echo "📝 2. 最新提交..."
git log -1 --oneline
echo ""

# 3. 等待 GitHub Pages 部署
echo "⏳ 3. 等待 GitHub Pages 部署（30 秒）..."
sleep 30
echo ""

# 4. 检查页面是否可访问
echo "🌐 4. 检查页面可访问性..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL")
if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ 页面可访问（HTTP $HTTP_CODE）"
else
  echo "❌ 页面访问失败（HTTP $HTTP_CODE）"
  exit 1
fi
echo ""

# 5. 检查 AI 新闻板块
echo "🤖 5. 检查 AI 新闻板块..."
PAGE_CONTENT=$(curl -s "$SITE_URL")

AI_NEWS_COUNT=$(echo "$PAGE_CONTENT" | grep -c "🤖 AI 新闻" || true)
if [ "$AI_NEWS_COUNT" -eq 0 ]; then
  echo "❌ 未找到 AI 新闻板块"
  exit 1
elif [ "$AI_NEWS_COUNT" -gt 1 ]; then
  echo "⚠️  警告：发现 $AI_NEWS_COUNT 个 AI 新闻板块（预期 1 个）"
else
  echo "✅ AI 新闻板块正常（1 个）"
fi

# 提取新闻数量
BADGE_COUNT=$(echo "$PAGE_CONTENT" | grep -A 1 "🤖 AI 新闻" | grep -oP 'badge">\K\d+' || echo "0")
echo "   📊 新闻数量：$BADGE_COUNT 条"

# 检查轮播元素
if echo "$PAGE_CONTENT" | grep -q "carousel-btn"; then
  echo "✅ 轮播按钮存在"
else
  echo "⚠️  警告：未找到轮播按钮"
fi

if echo "$PAGE_CONTENT" | grep -q "carousel-dot"; then
  DOT_COUNT=$(echo "$PAGE_CONTENT" | grep -c "carousel-dot" || true)
  PAGES=$((DOT_COUNT / 2))  # 每个 dot 出现 2 次（class 和 data-page）
  echo "✅ 轮播指示器存在（$PAGES 页）"
else
  echo "⚠️  警告：未找到轮播指示器"
fi
echo ""

# 6. 检查主线结论
echo "📊 6. 检查主线结论..."
if echo "$PAGE_CONTENT" | grep -q "主线结论"; then
  THESIS_TIME=$(echo "$PAGE_CONTENT" | grep -oP '主线结论.*?hero-time">\K[^<]+' | head -1)
  echo "✅ 主线结论存在（更新时间：$THESIS_TIME）"
else
  echo "❌ 未找到主线结论"
fi
echo ""

# 7. 检查各板块
echo "📰 7. 检查新闻板块..."
SECTION_COUNT=$(echo "$PAGE_CONTENT" | grep -c '<section class="card">' || true)
echo "   总板块数：$SECTION_COUNT"

for SECTION in "指数/科技" "能源/地缘" "美联储/政策"; do
  if echo "$PAGE_CONTENT" | grep -q "$SECTION"; then
    COUNT=$(echo "$PAGE_CONTENT" | grep -A 1 "$SECTION" | grep -o 'badge">[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0")
    echo "   ✅ $SECTION ($COUNT 条)"
  else
    echo "   ⚠️  $SECTION（未找到）"
  fi
done
echo ""

# 8. 汇总
echo "✅ 检查完成！"
echo ""
echo "🔗 查看页面：$SITE_URL"
echo "📅 检查时间：$(date '+%Y-%m-%d %H:%M:%S')"
