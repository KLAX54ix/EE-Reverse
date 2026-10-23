# Bring EduEditer to the foreground and send a real left click at screen (X, Y).
# Used to re-bind the text caret after a canvas insert (the engine moves focus
# into the new canvas; a real click into page text is the only reliable way
# back, and SetForegroundWindow needs the AttachThreadInput trick from a
# non-foreground process).
param(
  [Parameter(Mandatory=$true)][int]$X,
  [Parameter(Mandatory=$true)][int]$Y,
  [int]$DelayMs = 250
)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class EEClick {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pidOut);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  public const uint LD = 0x0002, LU = 0x0004;
}
'@
$script:t = [IntPtr]::Zero
$cb = [EEClick+EnumProc]{
  param($h, $l)
  $sb = New-Object System.Text.StringBuilder 512
  [void][EEClick]::GetWindowTextW($h, $sb, 512)
  if ($sb.ToString() -like 'Editer*') { $script:t = $h }
  return $true
}
[void][EEClick]::EnumWindows($cb, [IntPtr]::Zero)
if ($script:t -eq [IntPtr]::Zero) { Write-Host 'ERROR: Editer window not found'; exit 1 }
$fg = [EEClick]::GetForegroundWindow()
$procId = 0
$fgTid = [EEClick]::GetWindowThreadProcessId($fg, [ref]$procId)
$myTid = [EEClick]::GetCurrentThreadId()
[void][EEClick]::AttachThreadInput($myTid, $fgTid, $true)
[void][EEClick]::ShowWindow($script:t, 9)
[void][EEClick]::SetForegroundWindow($script:t)
[void][EEClick]::AttachThreadInput($myTid, $fgTid, $false)
Start-Sleep -Milliseconds 350
$fg2 = [EEClick]::GetForegroundWindow()
$sb2 = New-Object System.Text.StringBuilder 512
[void][EEClick]::GetWindowTextW($fg2, $sb2, 512)
if ($fg2 -ne $script:t) {
  Write-Host ("WARN: foreground is [" + $sb2.ToString() + "], not Editer")
}
[void][EEClick]::SetCursorPos($X, $Y)
Start-Sleep -Milliseconds 180
[EEClick]::mouse_event([EEClick]::LD, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 70
[EEClick]::mouse_event([EEClick]::LU, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds $DelayMs
Write-Host ("clicked " + $X + "," + $Y + " fg=[" + $sb2.ToString() + "]")
