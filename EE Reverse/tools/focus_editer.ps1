# Focus the EduEditer main window WITHOUT Get-Process (process enumeration is
# blocked in the sandbox).  EnumWindows + titles only.
#   pwsh -File focus_editer.ps1 [-Match 'EduEditer|\.wsd|慈溪'] [-Capture path.png]
param(
  [string]$Match = 'EduEditer|\.wsd|慈溪|Editer',
  [string]$Capture = ''
)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class FWin {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static List<IntPtr> All() {
    var list = new List<IntPtr>();
    EnumWindows(delegate(IntPtr h, IntPtr p) { list.Add(h); return true; }, IntPtr.Zero);
    return list;
  }
  public static string Title(IntPtr h) {
    var sb = new StringBuilder(512); GetWindowTextW(h, sb, sb.Capacity); return sb.ToString();
  }
}
"@

$cands = @()
foreach ($h in [FWin]::All()) {
  $t = [FWin]::Title($h)
  if (-not $t) { continue }
  if ($t -notmatch $Match) { continue }
  $r = New-Object FWin+RECT
  if (-not [FWin]::GetWindowRect($h, [ref]$r)) { continue }
  $w = $r.R - $r.L; $ht = $r.B - $r.T
  if ($w -le 0 -or $ht -le 0) { continue }
  $cands += [pscustomobject]@{ Hwnd=$h; L=$r.L; T=$r.T; W=$w; H=$ht;
    Vis=[FWin]::IsWindowVisible($h); Iconic=[FWin]::IsIconic($h); Title=$t }
}
if (-not $cands) { Write-Output "no window matched /$Match/"; exit 1 }
$cands | Sort-Object @{E={$_.W*$_.H};Descending=$true} | Format-Table -AutoSize | Out-String | Write-Host

$win = $cands | Sort-Object @{E={ if ($_.Title) {0} else {1} }}, @{E={$_.W*$_.H};Descending=$true} | Select-Object -First 1
Write-Host ("picked hwnd=0x{0:x} title='{1}' {2}x{3}" -f [int64]$win.Hwnd, $win.Title, $win.W, $win.H)

if ($win.Iconic) { [FWin]::ShowWindow($win.Hwnd, 9) | Out-Null; Start-Sleep -Milliseconds 600 }
[FWin]::ShowWindow($win.Hwnd, 9) | Out-Null
[FWin]::BringWindowToTop($win.Hwnd) | Out-Null
[FWin]::SetForegroundWindow($win.Hwnd) | Out-Null
Start-Sleep -Milliseconds 500
$fg = [FWin]::GetForegroundWindow()
Write-Host ("foreground=0x{0:x} target=0x{1:x} match={2}" -f [int64]$fg, [int64]$win.Hwnd, ($fg -eq $win.Hwnd))

if ($Capture) {
  $r2 = New-Object FWin+RECT
  [FWin]::GetWindowRect($win.Hwnd, [ref]$r2) | Out-Null
  $cw = $r2.R - $r2.L; $ch = $r2.B - $r2.T
  if ($cw -gt 0 -and $ch -gt 0) {
    $bmp = New-Object System.Drawing.Bitmap($cw, $ch)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [FWin]::PrintWindow($win.Hwnd, $hdc, [uint32]2)
    $g.ReleaseHdc($hdc); $g.Dispose()
    $bmp.Save($Capture, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    Write-Host "captured ok=$ok $cw x $ch -> $Capture  (rect $($r2.L),$($r2.T))"
  }
}
Write-Host "rect: $($win.L),$($win.T)"
