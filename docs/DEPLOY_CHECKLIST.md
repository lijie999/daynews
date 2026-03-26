# DayNews 发布检查清单

## 每次发布后必做检查

### 自动检查脚本
```bash
cd ~/.openclaw/workspace/daynews
./scripts/post-deploy-check.sh
```

**检查项目**：
1. ✅ 本地 Git 状态（无未提交更改）
2. ✅ 最新提交信息
3. ✅ GitHub Pages 可访问性（HTTP 200）
4. ✅ AI 新闻板块数量（预期 1 个）
5. ✅ 新闻条目数量（显示在 badge 中）
6. ✅ 轮播按钮存在
7. ✅ 轮播指示器存在（页数正确）
8. ✅ 主线结论存在（含更新时间）
9. ✅ 各板块新闻数量（指数/科技、能源/地缘、美联储/政策）

---

## 手动检查清单（首次发布 / 重大更新）

### 视觉检查
- [ ] 页面布局正常，无错位
- [ ] AI 新闻板块在主线结论后、grid3 前
- [ ] 轮播按钮 ‹ › 可点击
- [ ] 圆点指示器响应点击
- [ ] 新闻标题可点击跳转
- [ ] 标签颜色正确（融资红、监管灰、模型红、应用蓝）

### 交互测试
- [ ] 点击 ‹ 按钮：翻到上一页
- [ ] 点击 › 按钮：翻到下一页
- [ ] 点击圆点：跳转到对应页
- [ ] 按键盘 ← 键：翻到上一页
- [ ] 按键盘 → 键：翻到下一页
- [ ] 当前页圆点高亮显示（橙色长条）
- [ ] 翻页动画流畅

### 内容验证
- [ ] 新闻来源链接正确
- [ ] 新闻标题准确
- [ ] 摘要长度合适（≤200字符）
- [ ] 分类标签准确（融资/模型/监管等）
- [ ] 无重复新闻
- [ ] 时间戳更新

### 移动端测试（可选）
- [ ] 手机浏览器布局正常
- [ ] 轮播按钮大小适中
- [ ] 触摸滑动翻页（如果实现）

---

## 常见问题排查

### 问题：AI 新闻显示"今日暂无 AI 新闻"
**原因**：
1. 采集脚本失败（API 超限、RSS 被阻止）
2. 注入脚本解析失败（格式不匹配）

**检查**：
```bash
# 查看最新采集文件
ls -lt ~/.openclaw/workspace/skills/ai-news-zh/outputs/*.md | head -3

# 查看文件内容
cat ~/.openclaw/workspace/skills/ai-news-zh/outputs/2026-03-26-*.md | tail -1

# 手动运行注入脚本
cd ~/.openclaw/workspace/daynews
python3 scripts/inject_ai_news.py
```

### 问题：出现多个 AI 新闻板块
**原因**：注入脚本的删除正则表达式失效

**修复**：
```bash
cd ~/.openclaw/workspace/daynews
# 查看 index.html 中 AI 新闻板块数量
grep -c "🤖 AI 新闻" docs/index.html

# 手动重新注入
python3 scripts/inject_ai_news.py
```

### 问题：轮播按钮不工作
**原因**：JavaScript 未正确注入或冲突

**检查**：
```bash
# 查看是否包含 JavaScript
grep "aiNewsCarousel" docs/index.html

# 浏览器控制台检查是否有 JS 错误
```

---

## 快速发布流程

```bash
# 1. 修改代码
vim scripts/inject_ai_news.py

# 2. 本地测试
python3 scripts/inject_ai_news.py

# 3. 提交并推送
git add -A
git commit -m "描述更改内容"
git push

# 4. 等待 30 秒后检查
sleep 30
./scripts/post-deploy-check.sh

# 5. 手动浏览器验证
open https://lijie999.github.io/daynews/
```

---

## 自动化建议

### 添加 Git Hook（可选）
在 `.git/hooks/post-commit` 中添加：
```bash
#!/bin/bash
echo "💡 提示：记得运行 post-deploy-check.sh 检查部署"
```

### 添加 GitHub Actions（高级）
创建 `.github/workflows/check-deploy.yml` 自动运行检查脚本。

---

**记录时间**：2026-03-26 17:20  
**版本**：稳定版 v1.0  
**维护者**：OpenClaw Agent
