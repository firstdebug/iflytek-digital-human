#!/bin/bash
# 验证 skills 中所有 setGlobalParams Web 示例是否包含完整的 avatar.stream 结构

cd "$(dirname "$0")/.."
SKILLS_DIR="skills"

echo "=== 检查 Web SDK setGlobalParams 完整性 ==="
echo ""

INCOMPLETE=0
CHECKED=0

# 查找所有包含 setGlobalParams 的 markdown 文件
while IFS= read -r file; do
  # 提取 setGlobalParams 代码块及其后20行
  if grep -Pzo '(?s)avatar\.setGlobalParams\(\{[^}]*avatar:\s*\{[^}]{0,500}\}' "$file" | grep -q "avatar.*stream.*protocol"; then
    # 包含 avatar.stream.protocol，认为是完整的
    : # pass
  else
    # 检查是否是 Web 平台的示例（排除只展示片段的文件）
    if grep -A30 "setGlobalParams" "$file" | grep -q "avatar:\s*{" && \
       ! grep -A30 "setGlobalParams" "$file" | grep -q "avatar.*stream.*protocol"; then
      echo "⚠️  缺少完整 avatar.stream: $file"
      INCOMPLETE=$((INCOMPLETE + 1))
    fi
  fi
  CHECKED=$((CHECKED + 1))
done < <(grep -rl "setGlobalParams" "$SKILLS_DIR" --include="*.md" 2>/dev/null)

echo ""
echo "=== 检查完成 ==="
echo "检查文件数: $CHECKED"
echo "不完整示例: $INCOMPLETE"

if [ $INCOMPLETE -eq 0 ]; then
  echo "✅ 所有 Web SDK setGlobalParams 示例均包含完整 avatar.stream 结构"
  exit 0
else
  echo "❌ 发现 $INCOMPLETE 个不完整示例，需要修复"
  exit 1
fi
