# Build do Transcritor de Áudio (PowerShell 7)
# Uso:  .\build.ps1          -> gera dist\transcrizap.exe
#       .\build.ps1 -Zip     -> além do exe, gera o zip de distribuição
param(
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$Version = '2.4.0'
$ProjectDir = $PSScriptRoot
$ExePath = Join-Path $ProjectDir 'dist\transcrizap.exe'
$ZipPath = Join-Path $ProjectDir "Transcritor-de-Audio-de-Zap-v$Version-win64.zip"
$LeiaMe = Join-Path $ProjectDir 'distribuicao\LEIA-ME.txt'

Write-Host '============================================'
Write-Host " Transcritor de Audio de Zap - Build v$Version"
Write-Host '============================================'

# (a) Checar Python
Write-Host ''
Write-Host '[1/4] Verificando Python...'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host 'ERRO: Python nao encontrado no PATH. Instale Python 3.10+ (https://www.python.org).'
    exit 1
}
$pyVersion = & python --version
Write-Host "      $pyVersion em $($python.Source)"

# (b) Instalar dependências (inclui pyinstaller, fixado no requirements.txt)
Write-Host ''
Write-Host '[2/4] Instalando dependencias (requirements.txt)...'
& python -m pip install -r (Join-Path $ProjectDir 'requirements.txt') --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERRO ao instalar dependencias. Verifique as mensagens acima.'
    exit 1
}

# (c) Baixar e verificar o ffmpeg estatico (compactacao de audio acima de 25MB)
# Build LGPL (sem codecs GPL-only; libopus, que usamos, e livre) do BtbN
# FFmpeg-Builds. A tag "latest" do BtbN e recriada periodicamente (nao ha
# releases datados/imutaveis nesse projeto) - por isso fixamos o SHA256 do
# arquivo atual: se o upstream trocar o conteudo, o hash nao vai bater e o
# build para aqui, avisando para reconfirmar URL+hash em vez de aceitar um
# binario diferente do validado.
# Cache FORA do projeto (mesma razao do $WorkPath abaixo): o Google Drive
# sincroniza a pasta do projeto e um binario de ~110MB re-sincronizando a
# cada build so causaria travamento/lentidao para nada, já que o binário
# não muda entre builds.
$FfmpegCacheDir = Join-Path $env:LOCALAPPDATA 'transcritor-build\vendor\ffmpeg'
$FfmpegExe = Join-Path $FfmpegCacheDir 'ffmpeg.exe'
$FfmpegUrl = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-lgpl-8.1.zip'
$FfmpegSha256 = '6e905b675185c13a267e961e2d0a47d07293f4f90d3e6e29d1f809409d8e938a'
Write-Host ''
Write-Host '[3/4] Verificando ffmpeg.exe (compactacao de audio)...'
if (Test-Path $FfmpegExe) {
    Write-Host "      OK, ja em cache: $FfmpegExe"
} else {
    Write-Host '      Nao encontrado em cache. Baixando build LGPL estatico (BtbN)...'
    $FfmpegZip = Join-Path $env:TEMP 'transcritor-ffmpeg-download.zip'
    Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegZip
    $actualHash = (Get-FileHash -Path $FfmpegZip -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -ne $FfmpegSha256) {
        Remove-Item $FfmpegZip -Force
        Write-Host "ERRO: SHA256 do download do ffmpeg nao confere."
        Write-Host "      Esperado: $FfmpegSha256"
        Write-Host "      Obtido:   $actualHash"
        Write-Host "      O build de origem (BtbN) pode ter sido atualizado - reconfirme a URL e o hash em build.ps1."
        exit 1
    }
    $FfmpegExtract = Join-Path $env:TEMP 'transcritor-ffmpeg-extract'
    if (Test-Path $FfmpegExtract) { Remove-Item $FfmpegExtract -Recurse -Force }
    Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract
    $foundExe = Get-ChildItem -Path $FfmpegExtract -Filter 'ffmpeg.exe' -Recurse | Select-Object -First 1
    if (-not $foundExe) {
        Write-Host 'ERRO: ffmpeg.exe nao encontrado dentro do zip baixado.'
        exit 1
    }
    New-Item -ItemType Directory -Force -Path $FfmpegCacheDir | Out-Null
    Copy-Item -Path $foundExe.FullName -Destination $FfmpegExe -Force
    Remove-Item $FfmpegZip -Force
    Remove-Item $FfmpegExtract -Recurse -Force
    Write-Host "      OK, baixado e verificado: $FfmpegExe"
}
$env:TRANSCRITOR_FFMPEG_PATH = $FfmpegExe

# (d) Build com PyInstaller
# Workpath FORA do projeto: o Google Drive sincroniza a pasta do projeto e trava
# os temporarios do build (PermissionError no --clean). So o exe final vai para dist\.
$WorkPath = Join-Path $env:LOCALAPPDATA 'Temp\transcritor-build'
Write-Host ''
Write-Host '[4/4] Gerando o executavel (PyInstaller)...'
& python -m PyInstaller (Join-Path $ProjectDir 'transcritor.spec') --noconfirm --clean --distpath (Join-Path $ProjectDir 'dist') --workpath $WorkPath
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERRO no build. Verifique as mensagens acima.'
    exit 1
}

# (e) Resultado
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

# (f) Zip de distribuição (opcional)
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
