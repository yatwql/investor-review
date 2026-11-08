# scripts/launch.ps1 - 投资分析 TUI 启动脚本 (Windows)
# Encoding: UTF-8 with BOM (PowerShell requires BOM for Chinese chars)

# 获取项目根目录（使脚本可以从任意目录运行）
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

# 应用名称（与 src/python/core/constants.py 的 APP_NAME 保持一致；shell 无法直接 import，此处同步维护）
Write-Host "正在启动投资复盘助手 ..."
Write-Host "项目目录: $projectRoot"

# 0. 解析入口参数（默认 TUI；web 入口启动轻量 Web 服务，参数透传 --host/--port/--config）
$entry = "tui"
$entryArgs = @($args)
if ($args.Count -gt 0 -and ($args[0] -eq "web" -or $args[0] -eq "tui")) {
    $entry = $args[0]
    if ($args.Count -gt 1) {
        $entryArgs = @($args[1..($args.Count - 1)])
    } else {
        $entryArgs = @()
    }
}

# 1. 检查 Python 是否安装
$pythonCmd = $null
try {
    $null = Get-Command "python" -ErrorAction Stop
    $pythonCmd = "python"
} catch {
    try {
        $null = Get-Command "python3" -ErrorAction Stop
        $pythonCmd = "python3"
    } catch {
        Write-Host "错误: 未找到 Python，请先安装 Python 环境。" -ForegroundColor Red
        exit 1
    }
}

Write-Host "检测到 Python: $($pythonCmd)"

# 2. 检查/创建虚拟环境
function _Ensure-VenvInitialized {
    param([string]$Path)
    $activateScript = Join-Path $Path "Scripts\Activate.ps1"
    $pyvenvCfg = Join-Path $Path "pyvenv.cfg"
    if (-not (Test-Path $activateScript) -and -not (Test-Path $pyvenvCfg)) {
        Write-Host "虚拟环境目录为空，正在创建: $Path" -ForegroundColor Yellow
        & $pythonCmd -m venv $Path
        if (-not (Test-Path $Path)) {
            Write-Host "错误: 创建虚拟环境失败: $Path" -ForegroundColor Red
            exit 1
        }
        Write-Host "虚拟环境创建完成: $Path" -ForegroundColor Cyan
    }
}

if (Test-Path ".venv") {
    $item = Get-Item ".venv"
    if ($item.LinkType -eq "Junction") {
        $venvTarget = $item.Target
        Write-Host "检测到外部虚拟环境链接: $venvTarget" -ForegroundColor Cyan
        _Ensure-VenvInitialized -Path $venvTarget
    } else {
        Write-Host "检测到本地虚拟环境。" -ForegroundColor Cyan
        _Ensure-VenvInitialized -Path ".venv"
    }
} elseif ($env:VENV_PATH) {
    # VENV_PATH 环境变量指向外部管理的 .venv 目录
    $externalVenv = $env:VENV_PATH
    Write-Host "正在链接外部虚拟环境: $externalVenv" -ForegroundColor Cyan
    if (-not (Test-Path $externalVenv)) {
        Write-Host "外部虚拟环境目录不存在，正在创建: $externalVenv" -ForegroundColor Yellow
        & $pythonCmd -m venv $externalVenv
        if (-not (Test-Path $externalVenv)) {
            Write-Host "错误: 创建外部虚拟环境失败。" -ForegroundColor Red
            exit 1
        }
    }
    _Ensure-VenvInitialized -Path $externalVenv
    New-Item -ItemType Junction -Path ".venv" -Target $externalVenv | Out-Null
    Write-Host "已创建链接: .venv → $externalVenv" -ForegroundColor Cyan
} else {
    Write-Host "正在创建本地虚拟环境 ..."
    Write-Host "提示: 设置 VENV_PATH 环境变量可将 .venv 管理在项目外部。" -ForegroundColor DarkGray
    & $pythonCmd -m venv .venv
    if (-not (Test-Path ".venv")) {
        Write-Host "错误: 创建虚拟环境失败。" -ForegroundColor Red
        exit 1
    }
}

# 3. 定位虚拟环境解释器（不依赖 Activate.ps1）
# 不使用 `. Activate.ps1`：激活脚本内烘焙的是**绝对** VIRTUAL_ENV 路径，venv 目录被移动/
# 改软链位置后它仍指向旧路径，PATH 前置失效 → 裸 python/python3 落到系统解释器，
# 表现为跑到中途 ModuleNotFoundError: No module named 'pandas'。此处直接调用 venv 内解释器。
Write-Host "正在定位虚拟环境解释器 ..."
if (Test-Path ".\.venv\Scripts\python.exe") {
    $venvPy = ".\.venv\Scripts\python.exe"
}
elseif (Test-Path ".\.venv\bin\python") {
    $venvPy = ".\.venv\bin\python"
}
else {
    Write-Host "错误: 未找到虚拟环境解释器（.\.venv\Scripts\python.exe 或 .\.venv\bin\python）。" -ForegroundColor Red
    Write-Host "提示: 删除 .venv 后重新运行本脚本，或确认 VENV_PATH 指向的环境已就绪。" -ForegroundColor DarkGray
    exit 1
}
Write-Host "虚拟环境解释器: $venvPy" -ForegroundColor Cyan

# 3.5. 检查 Python 版本（要求 >= 3.10）
$pyVer = & $venvPy -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$verParts = $pyVer.Split('.')
$major = [int]$verParts[0]
$minor = [int]$verParts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Host "错误: 需要 Python >= 3.10，当前版本: $pyVer" -ForegroundColor Red
    exit 1
}
Write-Host "Python 版本: $pyVer（满足要求）" -ForegroundColor Cyan

# 4. 安装依赖（检查 requirements.txt 是否变更，未变更则跳过）
$depsMarker = ".venv\.deps_installed"
$reqHash = (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash
$skipInstall = $false
if (Test-Path $depsMarker) {
    $oldHash = (Get-Content $depsMarker -Raw).Trim()
    if ($oldHash -eq $reqHash) {
        $skipInstall = $true
    }
}
if (-not $skipInstall) {
    Write-Host "正在安装依赖 ..."
    try {
        # -qq 级静默：抑制 pip 版本通知和下载进度条
        # 用 python -m pip 而非 pip：pip.exe 启动器硬编码创建时的 Python 绝对路径，
        # venv 被复制/移动后会指向旧路径报 Fatal error in launcher
        & $venvPy -m pip install -qq -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Set-Content -Path $depsMarker -Value $reqHash
        }
    } catch {
        Write-Host "错误: 安装依赖失败。" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "依赖已安装，跳过 pip install（requirements.txt 未变更）" -ForegroundColor DarkGray
}

# 5. 创建所需目录
Write-Host "正在创建数据目录 ..."
New-Item -ItemType Directory -Force -Path "data\holdings" | Out-Null
New-Item -ItemType Directory -Force -Path "data\cache" | Out-Null
New-Item -ItemType Directory -Force -Path "data\config" | Out-Null
New-Item -ItemType Directory -Force -Path "docs\tmp" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# 6. 启动前硬闸：解释器必须能导入重依赖
# 与上面的「解释器定位」互补：.venv 存在但半装时，跑到数据准备阶段才报
# ModuleNotFoundError，用户看到的是一份失败报告而非可读错误。
$null = & $venvPy -c "import pandas, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: $venvPy 缺少关键依赖（pandas / numpy），无法生成报告。" -ForegroundColor Red
    Write-Host "请安装依赖: $venvPy -m pip install -r requirements.txt" -ForegroundColor DarkGray
    exit 1
}

# 7. 启动主程序
if ($entry -eq "web") {
    Write-Host "正在启动 Web 服务（http://127.0.0.1:8000，Ctrl+C 退出）..." -ForegroundColor Cyan
    Write-Host "(提示: 局域网访问用 launch.ps1 web --host 0.0.0.0)" -ForegroundColor DarkGray
    try {
        & $venvPy src\python\web\server.py @entryArgs
    } catch {
        Write-Host "错误: 程序运行失败: $_" -ForegroundColor Red
    }
} else {
    Write-Host "正在启动主程序 ..."
    try {
        & $venvPy src\python\tui\tui.py
    } catch {
        Write-Host "错误: 程序运行失败: $_" -ForegroundColor Red
    }
}
