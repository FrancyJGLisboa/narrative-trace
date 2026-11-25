# Narrative Trace one-line installer (Windows PowerShell).
#   irm https://raw.githubusercontent.com/FrancyJGLisboa/narrative-trace/main/install.ps1 | iex
# Options via environment variables before running: $env:NT_HARNESS = "cursor"; $env:NT_SCOPE = "project"
$ErrorActionPreference = "Stop"
$Repo = "https://github.com/FrancyJGLisboa/narrative-trace"
$Dest = if ($env:NT_INSTALL_DIR) { $env:NT_INSTALL_DIR } else { Join-Path $HOME ".narrative-trace" }
$Harness = if ($env:NT_HARNESS) { $env:NT_HARNESS } else { "auto" }
$Scope = if ($env:NT_SCOPE) { $env:NT_SCOPE } else { "user" }

$Py = $null
foreach ($c in @("py", "python", "python3")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    $args0 = if ($c -eq "py") { @("-3") } else { @() }
    & $c @args0 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $Py = $c; $PyArgs = $args0; break }
  }
}
if (-not $Py) { throw "narrative-trace: Python 3.9+ is required." }

if (Get-Command git -ErrorAction SilentlyContinue) {
  if (Test-Path (Join-Path $Dest ".git")) { git -C $Dest pull -q --ff-only } else { git clone -q --depth 1 $Repo $Dest }
} else {
  $zip = Join-Path $env:TEMP "narrative-trace.zip"
  Invoke-WebRequest "$Repo/archive/refs/heads/main.zip" -OutFile $zip
  $tmp = Join-Path $env:TEMP "narrative-trace-src"
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive $zip -DestinationPath $tmp
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  Copy-Item (Join-Path $tmp "narrative-trace-main\*") $Dest -Recurse -Force
}
& $Py @PyArgs (Join-Path $Dest "ntrace.py") install --harness $Harness --scope $Scope --project (Get-Location).Path
Write-Host "Done. Uninstall: $Py $(Join-Path $Dest 'ntrace.py') uninstall --harness all --scope $Scope"
