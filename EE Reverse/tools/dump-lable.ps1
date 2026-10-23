$ErrorActionPreference = 'Stop'
$env:JAVA_HOME = 'D:\java'
$ghidra = 'D:\EE Reverse\tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat'
$proj   = 'D:\EE Reverse\analysis\ghidra-proj'
$script = 'D:\EE Reverse\tools\ghidra-scripts\DumpDecomp.java'
$out    = 'D:\EE Reverse\analysis\decomp-lable2.txt'

if (-not (Test-Path $ghidra)) { Write-Host "MISSING $ghidra"; exit 1 }
if (-not (Test-Path $script)) { Write-Host "MISSING $script"; exit 1 }

& $ghidra $proj EEeslib `
    -process eslib.dll `
    -scriptPath 'D:\EE Reverse\tools\ghidra-scripts' `
    -postScript DumpDecomp.java $out `
    saveprop loadprop epgetproplablestring recalcLayoutLable initialize@esseglable Build@esseglable

Write-Host "exit=$LASTEXITCODE"
if (Test-Path $out) { Write-Host ("out bytes = " + (Get-Item $out).Length) }
