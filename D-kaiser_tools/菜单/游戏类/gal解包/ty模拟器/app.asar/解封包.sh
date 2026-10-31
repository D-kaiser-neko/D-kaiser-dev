#!/data/data/com.termux/files/usr/bin/bash
# 自动检测并安装 app.asar 解包/打包依赖 (Termux 专用)

echo "🔍 正在检测依赖环境..."

# ---------- 检测 Node.js ----------
if command -v node &> /dev/null; then
    echo "✅ Node.js 已安装: $(node -v)"
else
    echo "❌ Node.js 未安装，正在通过 pkg 安装..."
    pkg install nodejs -y
    if [ $? -eq 0 ]; then
        echo "✅ Node.js 安装成功"
    else
        echo "❌ 安装失败，请检查网络或手动执行: pkg install nodejs"
        exit 1
    fi
fi

# ---------- 检测 asar 全局命令 ----------
if command -v asar &> /dev/null; then
    echo "✅ asar 已全局安装 (版本: $(asar --version 2>/dev/null || echo '未知'))"
else
    echo "❌ asar 未安装，正在通过 npm 全局安装 @electron/asar ..."
    npm install -g @electron/asar
    if [ $? -eq 0 ]; then
        echo "✅ asar 安装成功"
    else
        echo "❌ 全局安装失败，尝试使用 npx 临时方案（无需安装）"
        if command -v npx &> /dev/null; then
            echo "⚠️  您可以使用 'npx asar' 代替 'asar' 命令，用法相同"
            echo "   例如: npx asar extract app.asar ./output"
        else
            echo "❌ npx 也不可用，请手动安装 asar: npm install -g @electron/asar"
            exit 1
        fi
    fi
fi

echo "🎉 依赖检查完成！"
echo ""
echo "📖 常用命令："
echo "  解包: asar extract app.asar ./output"
echo "  打包: asar pack ./output app.asar"
echo "   (若使用 npx，将 asar 替换为 npx asar)"