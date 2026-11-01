# Starts (or stops) the headed browser used for manual login, with remote
# debugging on the given port and a throwaway profile under the scratchpad.
# Uses the system Edge: Playwright's bundled Chromium fails its sandbox when
# the Windows user path has non-ASCII characters.
#   powershell -File browser.ps1 start <url> <scratchpad> [port]
#   powershell -File browser.ps1 stop  <scratchpad>
param(
  [Parameter(Mandatory)][ValidateSet('start', 'stop')][string]$Action,
  [string]$Url,
  [string]$Scratchpad,
  [int]$Port = 9222
)

if ($Action -eq 'stop') {
  $Scratchpad = $Url
  Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object { $_.CommandLine -like '*pw-profile*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
  Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like '*recorder.js*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
  Start-Sleep 2
  $profileDir = Join-Path $Scratchpad 'pw-profile'
  if (Test-Path -LiteralPath $profileDir) {
    # \\?\ prefix: Edge extension folders exceed MAX_PATH under the scratchpad.
    $full = (Resolve-Path -LiteralPath $profileDir).ProviderPath
    Remove-Item -LiteralPath "\\?\$full" -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue
  }
  "profile removed: $(-not (Test-Path -LiteralPath $profileDir))"
  return
}

$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge not found' }
$profileDir = Join-Path $Scratchpad 'pw-profile'
Start-Process -FilePath $edge -ArgumentList "--remote-debugging-port=$Port", "--user-data-dir=`"$profileDir`"", '--no-first-run', $Url
"started $Url on port $Port"
