# Build do Transcritor de Áudio (PowerShell 7)
# Uso:  .\build.ps1          -> gera dist\Transcritor de Audio de Zap.exe
#       .\build.ps1 -Zip     -> além do exe, gera o zip de distribuição
param(
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$Version = '2.2.0'
$ProjectDir = $PSScriptRoot
$ExePath = Join-Path $ProjectDir 'dist\Transcritor de Audio de Zap.exe'
$ZipPath = Join-Path $ProjectDir "Transcritor-de-Audio-de-Zap-v$Version-win64.zip"
$LeiaMe = Join-Path $ProjectDir 'distribuicao\LEIA-ME.txt'

Write-Host '============================================'
Write-Host " Transcritor de Audio de Zap - Build v$Version"
Write-Host '============================================'

# (a) Checar Python
Write-Host ''
Write-Host '[1/3] Verificando Python...'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host 'ERRO: Python nao encontrado no PATH. Instale Python 3.10+ (https://www.python.org).'
    exit 1
}
$pyVersion = & python --version
Write-Host "      $pyVersion em $($python.Source)"

# (b) Instalar dependências (inclui pyinstaller, fixado no requirements.txt)
Write-Host ''
Write-Host '[2/3] Instalando dependencias (requirements.txt)...'
& python -m pip install -r (Join-Path $ProjectDir 'requirements.txt') --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERRO ao instalar dependencias. Verifique as mensagens acima.'
    exit 1
}

# (c) Build com PyInstaller
# Workpath FORA do projeto: o Google Drive sincroniza a pasta do projeto e trava
# os temporarios do build (PermissionError no --clean). So o exe final vai para dist\.
$WorkPath = Join-Path $env:LOCALAPPDATA 'Temp\transcritor-build'
Write-Host ''
Write-Host '[3/3] Gerando o executavel (PyInstaller)...'
& python -m PyInstaller (Join-Path $ProjectDir 'transcritor.spec') --noconfirm --clean --distpath (Join-Path $ProjectDir 'dist') --workpath $WorkPath
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERRO no build. Verifique as mensagens acima.'
    exit 1
}

# (d) Resultado
if (-not (Test-Path $ExePath)) {
    Write-Host "ERRO: build terminou sem erro, mas o exe nao foi encontrado em: $ExePath"
    exit 1
}
$sizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
Write-Host ''
Write-Host '============================================'
Write-Host ' Build concluido.'
Write-Host " Executavel: $ExePath"
Write-Host " Tamanho:    $sizeMB MB"
Write-Host '============================================'

# (e) Zip de distribuição (opcional)
if ($Zip) {
    Write-Host ''
    Write-Host 'Gerando zip de distribuicao...'
    if (-not (Test-Path $LeiaMe)) {
        Write-Host "ERRO: arquivo de distribuicao nao encontrado: $LeiaMe"
        exit 1
    }
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Compress-Archive -Path $ExePath, $LeiaMe -DestinationPath $ZipPath -CompressionLevel Optimal
    $zipMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
    Write-Host "Zip pronto para enviar: $ZipPath ($zipMB MB)"
}
