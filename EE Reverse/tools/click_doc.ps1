Add-Type @"
using System;
using System.Runtime.InteropServices;
public class U {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public const uint LEFTDOWN = 0x0002, LEFTUP = 0x0004;
}
"@

$p = Get-Process Editer -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output 'no Editer window'; exit 1 }
$h = $p.MainWindowHandle
if ([U]::IsIconic($h)) { [U]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
[U]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 400

$wr = New-Object U+RECT; [U]::GetWindowRect($h, [ref]$wr) | Out-Null
$cr = New-Object U+RECT; [U]::GetClientRect($h, [ref]$cr) | Out-Null
Write-Output ("window rect: {0},{1} - {2},{3}  size {4}x{5}" -f $wr.L,$wr.T,$wr.R,$wr.B,($wr.R-$wr.L),($wr.B-$wr.T))
Write-Output ("client rect: {0}x{1}" -f $cr.R,$cr.B)

# screenshot coords (as produced by capture_window.ps1) -> screen coords
$shotX = [int]$args[0]; $shotY = [int]$args[1]
$sx = $wr.L + $shotX
$sy = $wr.T + $shotY
Write-Output ("clicking screen ({0},{1})  <= shot ({2},{3})" -f $sx,$sy,$shotX,$shotY)
[U]::SetCursorPos($sx, $sy) | Out-Null
Start-Sleep -Milliseconds 120
[U]::mouse_event([U]::LEFTDOWN, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 60
[U]::mouse_event([U]::LEFTUP, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 300
Write-Output 'clicked'
