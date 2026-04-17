$desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$folderName = [string]::Concat([char]0x6D4B, [char]0x8BD5, [char]0x6587, [char]0x4EF6, [char]0x5939)
$fullPath = Join-Path -Path $desktopPath -ChildPath $folderName

if (-not (Test-Path -LiteralPath $fullPath)) {
    New-Item -Path $fullPath -ItemType Directory -Force | Out-Null
    Write-Output $fullPath
}
else {
    Write-Output $fullPath
}