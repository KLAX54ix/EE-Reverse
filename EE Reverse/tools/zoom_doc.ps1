param(
  [int]$ShotX = 1100,
  [int]$ShotY = 655,
  [int]$Notches = 6,     # negative = zoom out
  [switch]$ClickFirst
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Z {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public const uint LEFTDOWN = 0x0002, LEFTUP = 0x0004, WHEEL = 0x0800;
  public const byte VK_CONTROL = 0x11;
  public const uint KEYUP = 0x0002;
}
"@
$p = Get-Process Editer -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output 'no Editer window'; exit 1 }
$h = $p.MainWindowHandle
if ([Z]::IsIconic($h)) { [Z]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
[Z]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 350
$wr = New-Object Z+RECT; [Z]::GetWindowRect($h, [ref]$wr) | Out-Null
$sx = $wr.L + $ShotX; $sy = $wr.T + $ShotY
[Z]::SetCursorPos($sx, $sy) | Out-Null
Start-Sleep -Milliseconds 120
if ($ClickFirst) {
  [Z]::mouse_event([Z]::LEFTDOWN, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 60
  [Z]::mouse_event([Z]::LEFTUP, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 250
}
[Z]::keybd_event([Z]::VK_CONTROL, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 60
$delta = [uint32]($Notches * 120)
for ($i = 0; $i -lt [Math]::Abs($Notches); $i++) {
  $d = if ($Notches -lt 0) { [uint32](-120) } else { [uint32]120 }
  [Z]::mouse_event([Z]::WHEEL, 0, 0, $d, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 80
}
[Z]::keybd_event([Z]::VK_CONTROL, 0, [Z]::KEYUP, [IntPtr]::Zero)
Start-Sleep -Milliseconds 300
Write-Output ("clicked=$ClickFirst notches=$Notches at ({0},{1})" -f $sx, $sy)
