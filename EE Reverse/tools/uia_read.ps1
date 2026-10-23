# Read visible text out of the Editer window using Windows UI Automation.
# Editer is MFC, so UIA may expose very little -- this reports what it finds.
param(
  [Parameter(Mandatory=$true)][string]$Hwnd,
  [int]$Max = 60
)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$h = [IntPtr][Convert]::ToInt64($Hwnd, 16)
$root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
if ($null -eq $root) { Write-Output 'FromHandle returned null'; exit 1 }
Write-Output ("ROOT: name='{0}' class='{1}'" -f $root.Current.Name, $root.Current.ClassName)

$cond = [System.Windows.Automation.Condition]::TrueCondition
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
Write-Output ("descendants: {0}" -f $all.Count)
$n = 0
foreach ($e in $all) {
  if ($n -ge $Max) { break }
  try {
    $c = $e.Current
    $t = ''
    try {
      $tp = $e.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
      if ($tp) { $t = $tp.DocumentRange.GetText(800) }
    } catch {}
    Write-Output ("[{0}] cls='{1}' name='{2}' text='{3}'" -f $n, $c.ClassName, $c.Name, ($t -replace "`r?`n", ' / '))
    $n++
  } catch {}
}
