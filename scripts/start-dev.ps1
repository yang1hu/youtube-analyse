$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$apiPort = if ($env:YCA_API_PORT) { $env:YCA_API_PORT } else { "8001" }
$apiTarget = if ($env:VITE_API_TARGET) { $env:VITE_API_TARGET } else { "http://127.0.0.1:$apiPort" }

Write-Host "Starting backend on http://127.0.0.1:$apiPort"
Start-Process -FilePath "python" `
  -ArgumentList "-m", "uvicorn", "creator_agent.main:app", "--host", "127.0.0.1", "--port", $apiPort `
  -WorkingDirectory $backend `
  -WindowStyle Hidden

Write-Host "Starting frontend on http://127.0.0.1:5173 with API target $apiTarget"
$frontendCommand = "set VITE_API_TARGET=$apiTarget&& npm.cmd run dev -- --host 127.0.0.1 --port 5173"
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c", $frontendCommand `
  -WorkingDirectory $frontend `
  -WindowStyle Hidden

Write-Host "Starting task worker"
Start-Process -FilePath "python" `
  -ArgumentList "-m", "creator_agent.worker" `
  -WorkingDirectory $backend `
  -WindowStyle Hidden

Write-Host "Open http://127.0.0.1:5173"
