
# ============================================================
# CAD4 - Development Cleanup
# Kullanım: .\clean.ps1
# ============================================================

$ErrorActionPreference = "Continue"

$Root = $PSScriptRoot

Write-Host "`nCAD4 CLEANUP" -ForegroundColor Cyan
Write-Host "Project: $Root`n"

# Silinecek klasörler
$CacheDirs = @(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox"
)

# Silinecek dosyalar
$CacheFiles = @(
    "*.pyc",
    "*.pyo",
    "*.pyd"
)

# 1. Cache klasörleri
Write-Host "[1/4] Cache directories..." -ForegroundColor Yellow

foreach ($name in $CacheDirs) {
    Get-ChildItem $Root -Directory -Filter $name -Recurse -Force |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# 2. Python cache dosyaları
Write-Host "[2/4] Python cache files..." -ForegroundColor Yellow

foreach ($pattern in $CacheFiles) {
    Get-ChildItem $Root -File -Filter $pattern -Recurse -Force |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

# 3. Build çıktıları
Write-Host "[3/4] Build directories..." -ForegroundColor Yellow

$BuildDirs = @("build", "dist")

foreach ($name in $BuildDirs) {
    $path = Join-Path $Root $name
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
    }
}

# 4. VS Code cache
Write-Host "[4/4] VS Code cache..." -ForegroundColor Yellow

$VSCodeCache = @(
    "$env:APPDATA\Code\Cache",
    "$env:APPDATA\Code\CachedData",
    "$env:APPDATA\Code\GPUCache",
    "$env:APPDATA\Code\Code Cache"
)

foreach ($path in $VSCodeCache) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "`nCleanup completed!" -ForegroundColor Green
Write-Host "CAD4 is ready.`n" -ForegroundColor Cyan
