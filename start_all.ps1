$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"

Write-Host "智慧消防 Agent V1.0.0 一键启动" -ForegroundColor Cyan

if (!(Test-Path (Join-Path $BackendDir "main.py"))) {
  Write-Host "未找到 backend/main.py，请确认脚本位于项目根目录。" -ForegroundColor Red
  pause
  exit 1
}

if (!(Test-Path (Join-Path $FrontendDir "package.json"))) {
  Write-Host "未找到 frontend/package.json，请确认脚本位于项目根目录。" -ForegroundColor Red
  pause
  exit 1
}

Set-Location $BackendDir
if (!(Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "正在创建 Python 3.14 虚拟环境..."
  py -3.14 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\pip.exe install -r requirements.txt

Set-Location $FrontendDir
if (!(Test-Path "node_modules")) {
  yarn install
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; .\.venv\Scripts\Activate.ps1; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; npm run dev"
Start-Sleep -Seconds 5

Start-Process "http://127.0.0.1:5173/dashboard"
Start-Process "http://127.0.0.1:8000/docs"

Write-Host "已启动。关闭弹出的两个 PowerShell 窗口即可停止服务。" -ForegroundColor Green
pause
