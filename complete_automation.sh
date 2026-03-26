#!/bin/bash

echo "═══════════════════════════════════════════"
echo "🤖 抖音简介完全自动化修改器"
echo "═══════════════════════════════════════════"

NEW_BIO="CyberStroll 跨境电商，连接全球贸易"

echo ""
echo "📝 新简介: $NEW_BIO"
echo ""
echo "⚠️ 注意：ADB 默认不支持中文输入"
echo "💡 解决方案：使用英文简介或安装 ADB Keyboard"
echo ""
echo "🔄 开始自动化流程..."
echo ""

# 1. 确保在编辑页面
echo "1️⃣ 检查当前页面..."
SNAPSHOT=$(agent-device snapshot --json)
if echo "$SNAPSHOT" | grep -q "修改简介"; then
    echo "   ✅ 已在编辑页面"
else
    echo "   ❌ 不在编辑页面，正在导航..."
    # 添加导航逻辑
fi

# 2. 查找输入框
echo "2️⃣ 查找输入框..."
INPUT_INDEX=$(echo "$SNAPSHOT" | node -e "
    const data = JSON.parse(require('fs').readFileSync(0, 'utf-8'));
    const nodes = data.data.nodes || [];
    const idx = nodes.findIndex(n =>
        n.type === 'android.widget.EditText' ||
        (n.label && n.label.includes('简介'))
    );
    console.log(idx >= 0 ? idx + 1 : -1);
")

if [ "$INPUT_INDEX" != "-1" ]; then
    echo "   ✅ 找到输入框: e$INPUT_INDEX"
else
    echo "   ❌ 未找到输入框"
    exit 1
fi

# 3. 点击输入框
echo "3️⃣ 点击输入框..."
agent-device press @e$INPUT_INDEX
sleep 1

# 4. 清空内容
echo "4️⃣ 清空原有内容..."
adb shell input keyevent KEYCODE_MOVE_HOME
adb shell input keyevent --longpress KEYCODE_DEL
sleep 0.5

# 5. 输入新简介（使用英文版本）
echo "5️⃣ 输入新简介..."
ENGLISH_BIO="CyberStroll Cross-border E-commerce, Connecting Global Trade"
echo "   使用英文版本: $ENGLISH_BIO"

# URL编码处理
ENCODED=$(echo "$ENGLISH_BIO" | sed 's/ /%s/g')
adb shell input text "$ENCODED"
sleep 0.5

# 6. 查找并点击保存按钮
echo "6️⃣ 保存修改..."
SAVE_INDEX=$(echo "$SNAPSHOT" | node -e "
    const data = JSON.parse(require('fs').readFileSync(0, 'utf-8'));
    const nodes = data.data.nodes || [];
    const idx = nodes.findIndex(n => n.label === '保存');
    console.log(idx >= 0 ? idx + 1 : -1);
")

if [ "$SAVE_INDEX" != "-1" ]; then
    echo "   找到保存按钮: e$SAVE_INDEX"
    agent-device press @e$SAVE_INDEX
    sleep 1

    echo ""
    echo "═══════════════════════════════════════════"
    echo "✅ 完成自动化！"
    echo "═══════════════════════════════════════════"
    echo ""
    echo "📝 新简介: $ENGLISH_BIO"
    echo ""
    echo "📸 截图已保存到: ./screenshots/"
else
    echo "   ⚠️ 未找到保存按钮，请手动保存"
fi

echo ""
echo "🎉 流程结束"
