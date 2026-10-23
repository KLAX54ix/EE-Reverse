# Mouse helper for the EduEditer window that does NOT rely on Get-Process
# (process enumeration is blocked in this sandbox).  Finds the window by title,
# restores+foregrounds it, then either scrolls the wheel or clicks a screen
# coordinate expressed RELATIVE TO THE WINDOW RECT (same convention as the
# PrintWindow/screencap screenshots).
#
#   pwsh -File mouse_editer.ps1 -Hwnd 0x5809c2 -Action scroll -X 1100 -Y 600 -Clicks -5
#   pwsh -File mouse_editer.ps1 -Action click -X 900 -Y 420 -Capture out.png
param(
  [string]$Hwnd = '',
  [string]$TitleMatch = 'Editer|EduEditer',
  [ValidateSet('click', 'dclick', 'scroll', 'none')][string]$Action = 'none',
  [int]$X = 0,
  [int]$Y = 0,
  [int]$Clicks = -3,
  [string]$Capture = ''
)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class MWin {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public const uint LEFTDOWN = 0x0002, LEFTUP = 0x0004, WHEEL = 0x0800;
  public static List<IntPtr> All() {
    var l = new List<IntPtr>();
    EnumWindows(delegate(IntPtr h, IntPtr p) { l.Add(h); return true; }, IntPtr.Zero);
    return l;
  }
  public static string Title(IntPtr h) {
    var sb = new StringBuilder(512); GetWindowTextW(h, sb, sb.Capacity); return sb.ToString();
  }
}
"@

$hw = [IntPtr]::Zero
if ($Hwnd) {
  $hw = [IntPtr][int64]([Convert]::ToInt64($Hwnd.TrimStart('0','x','X'), 16))
} else {
  foreach ($h in [MWin]::All()) {
    $t = [MWin]::Title($h)
    if ($t -and $t -match $TitleMatch) { $hw = $h; break }
  }
}
if ($hw -eq [IntPtr]::Zero) { Write-Output 'no window found'; exit 1 }

if ([MWin]::IsIconic($hw)) { [MWin]::ShowWindow($hw, 9) | Out-Null; Start-Sleep -Milliseconds 600 }
[MWin]::ShowWindow($hw, 9) | Out-Null
[MWin]::BringWindowToTop($hw) | Out-Null
[MWin]::SetForegroundWindow($hw) | Out-Null
Start-Sleep -Milliseconds 400
$r = New-Object MWin+RECT
[MWin]::GetWindowRect($hw, [ref]$r) | Out-Null
Write-Output ("hwnd=0x{0:x} rect={1},{2} {3}x{4} fg={5}" -f [int64]$hw, $r.L, $r.T, ($r.R-$r.L), ($r.B-$r.T), ([MWin]::GetForegroundWindow() -eq $hw))

$sx = $r.L + $X
$sy = $r.T + $Y
if ($Action -ne 'none') {
  [MWin]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 150
  if ($Action -eq 'click' -or $Action -eq 'dclick') {
    [MWin]::mouse_event([MWin]::LEFTDOWN, 0, 0, 0, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    [MWin]::mouse_event([MWin]::LEFTUP, 0, 0, 0, [IntPtr]::Zero)
    if ($Action -eq 'dclick') {
      Start-Sleep -Milliseconds 80
      [MWin]::mouse_event([MWin]::LEFTDOWN, 0, 0, 0, [IntPtr]::Zero)
      Start-Sleep -Milliseconds 60
      [MWin]::mouse_event([MWin]::LEFTUP, 0, 0, 0, [IntPtr]::Zero)
    }
    Start-Sleep -Milliseconds 350
  } elseif ($Action -eq 'scroll') {
    $n = [Math]::Abs($Clicks)
    $dir = if ($Clicks -lt 0) { 120 } else { -120 }   # +120 = wheel up
    for ($i = 0; $i -lt $n; $i++) {
      [MWin]::mouse_event([MWin]::WHEEL, 0, 0, $dir, [IntPtr]::Zero)
      Start-Sleep -Milliseconds 120
    }
    Start-Sleep -Milliseconds 400
  }
  Write-Output ("{0} at screen ({1},{2})" -f $Action, $sx, $sy)
}

if ($Capture) {
  [MWin]::GetWindowRect($hw, [ref]$r) | Out-Null
  $w = $r.R - $r.L; $h = $r.B - $r.T
  $bmp = New-Object System.Drawing.Bitmap($w, $h)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size($w, $h)))
  $g.Dispose()
  $bmp.Save($Capture, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Output "captured $w x $h -> $Capture"
}
