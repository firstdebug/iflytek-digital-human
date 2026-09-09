# 下载脚本（Bash / PowerShell）

## Bash 完整下载脚本

```bash
#!/bin/bash

# 虚拟人 Web SDK 自动下载脚本
# 版本: 3.2.3.1002

SDK_VERSION="3.2.3.1002"
SDK_FILENAME="avatar-sdk-web_${SDK_VERSION}.zip"
SDK_URL="https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-web-sdk.zip"
TARGET_DIR="./sdk"
TEMP_FILE="/tmp/avatar-sdk.zip"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          虚拟人 Web SDK 自动下载                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 1. 检查 SDK 是否已存在
if [ -d "${TARGET_DIR}/avatar-sdk-web_${SDK_VERSION}" ]; then
  echo "✅ SDK 已存在，跳过下载"
  echo ""
  echo "SDK 路径: ${TARGET_DIR}/avatar-sdk-web_${SDK_VERSION}/"
  exit 0
fi

# 2. 创建目标目录
mkdir -p "$TARGET_DIR"

# 3. 下载 SDK
echo "📥 正在下载 SDK..."
echo "版本: $SDK_VERSION"
echo "大小: ~5MB"
echo ""

# 使用 curl 下载，显示进度
if command -v curl &> /dev/null; then
  curl -L --progress-bar -o "$TEMP_FILE" "$SDK_URL"
  DOWNLOAD_STATUS=$?
elif command -v wget &> /dev/null; then
  wget --progress=bar:force -O "$TEMP_FILE" "$SDK_URL"
  DOWNLOAD_STATUS=$?
else
  echo "❌ 错误: 未找到 curl 或 wget"
  exit 1
fi

# 4. 检查下载是否成功
if [ $DOWNLOAD_STATUS -ne 0 ]; then
  echo "❌ 下载失败"
  echo ""
  echo "💡 可能原因:"
  echo "   - 网络连接问题"
  echo "   - 防火墙或代理拦截"
  echo ""
  echo "💡 备用方案:联系技术支持获取帮助"
  exit 1
fi

echo "✅ 下载完成"
echo ""

# 5. 解压 SDK
echo "📦 正在解压 SDK..."

unzip -q "$TEMP_FILE" -d "$TARGET_DIR"

if [ $? -ne 0 ]; then
  echo "❌ 解压失败"
  rm "$TEMP_FILE"
  exit 1
fi

echo "✅ 解压完成"
echo ""

# 6. 清理临时文件
rm "$TEMP_FILE"

# 7. 验证 SDK
echo "🔍 验证 SDK 完整性..."

SDK_PATH=$(find "$TARGET_DIR" -name "index.js" -path "*/avatar-sdk-web*" -type f | head -1 | xargs dirname)

if [ -n "$SDK_PATH" ]; then
  echo "✅ SDK 完整性验证通过"
  echo ""
  echo "SDK 路径: $SDK_PATH"
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║  ✅ SDK 下载和配置完成！                                  ║"
  echo "╚════════════════════════════════════════════════════════════╝"
else
  echo "❌ SDK 验证失败: 未找到 index.js"
  echo "请检查解压后的文件结构"
  exit 1
fi
```

## PowerShell 版本（Windows）

```powershell
# 虚拟人 SDK 自动下载 - Windows PowerShell

$SDK_VERSION = "3.2.3.1002"
$SDK_URL = "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-web-sdk.zip"
$TARGET_DIR = "./sdk"
$TEMP_FILE = "$env:TEMP/avatar-sdk.zip"

Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║          虚拟人 SDK 自动下载                               ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

# 1. 创建目标目录
New-Item -ItemType Directory -Force -Path $TARGET_DIR | Out-Null

# 2. 下载 SDK
Write-Host "📥 正在下载 SDK..."
Write-Host "版本: $SDK_VERSION"
Write-Host "大小: ~5MB"
Write-Host ""

try {
  # 使用 WebClient 下载
  $webClient = New-Object System.Net.WebClient
  $webClient.DownloadFile($SDK_URL, $TEMP_FILE)
  
  Write-Host "✅ 下载完成"
  Write-Host ""
} catch {
  Write-Host "❌ 下载失败: $_"
  Write-Host ""
  Write-Host "💡 备用方案:检查网络连接或联系技术支持"
  exit 1
}

# 3. 解压 SDK
Write-Host "📦 正在解压 SDK..."

try {
  Expand-Archive -Path $TEMP_FILE -DestinationPath $TARGET_DIR -Force
  Write-Host "✅ 解压完成"
  Write-Host ""
} catch {
  Write-Host "❌ 解压失败: $_"
  exit 1
}

# 4. 清理临时文件
Remove-Item $TEMP_FILE

# 5. 验证 SDK
Write-Host "🔍 验证 SDK 完整性..."

$indexJs = Get-ChildItem -Path $TARGET_DIR -Recurse -Filter "index.js" | Select-Object -First 1

if ($indexJs) {
  Write-Host "✅ SDK 完整性验证通过"
  Write-Host ""
  Write-Host "SDK 路径: $($indexJs.Directory.FullName)"
  Write-Host ""
  Write-Host "╔════════════════════════════════════════════════════════════╗"
  Write-Host "║  ✅ SDK 下载和配置完成！                                  ║"
  Write-Host "╚════════════════════════════════════════════════════════════╝"
} else {
  Write-Host "❌ SDK 不完整"
  exit 1
}
```

## 错误处理和备用方案

### 下载失败处理（镜像）

```bash
# 如果主下载链接失败，尝试备用链接
MIRRORS=(
  "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/avatar-web-sdk.zip"
)

for mirror in "${MIRRORS[@]}"; do
  echo "尝试镜像: $mirror"
  curl -L -o "$TEMP_FILE" "$mirror"
  
  if [ $? -eq 0 ]; then
    echo "✅ 从镜像下载成功"
    break
  fi
done

# 如果所有镜像都失败
if [ ! -f "$TEMP_FILE" ]; then
  echo "❌ 下载失败"
  echo ""
  echo "💡 请检查网络连接或联系技术支持获取帮助"
fi
```

### 网络代理支持

```bash
# 检测并使用系统代理
if [ -n "$HTTP_PROXY" ]; then
  echo "检测到代理: $HTTP_PROXY"
  export https_proxy=$HTTP_PROXY
fi

# 或使用 curl 的代理参数
curl -x http://proxy.example.com:8080 -L -o "$TEMP_FILE" "$SDK_URL"
```

## Demo 代码下载（可选）

### Web Demo

```bash
# 从 GitHub 或官方获取
git clone https://github.com/xfyun/avatar-web-demo.git
# 或
curl -L -o demo.zip https://doc.xfyun.cn/avatar/demo/web-demo.zip
```

### Android Demo

```bash
git clone https://github.com/xfyun/avatar-android-demo.git
```

