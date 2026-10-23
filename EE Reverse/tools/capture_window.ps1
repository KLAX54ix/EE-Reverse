# Capture a window of a target process to PNG, for visual verification.
#   pwsh -File capture_window.ps1 -ProcessName Editer -OutDir "D:\EE Reverse\captures"
param(
  [string]$ProcessName = 'Editer',
  [string]$OutDir = 'D:\EE Reverse\captures',
  [string]$Tag = 'ee'
)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WinCap {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

  public static List<IntPtr> WindowsOf(uint want) {
    var list = new List<IntPtr>();
    EnumWindows(delegate(IntPtr h, IntPtr p) {
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (pid == want) list.Add(h);
      return true;
    }, IntPtr.Zero);
    return list;
  }
  public static string TitleOf(IntPtr h) {
    var sb = new StringBuilder(512);
    GetWindowTextW(h, sb, sb.Capacity);
    return sb.ToString();
  }
}
"@

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$proc = Get-Process -Name $ProcessName -ErrorAction Stop | Select-Object -First 1
Write-Host "process $($proc.ProcessName) pid=$($proc.Id)"

$cands = @()
foreach ($h in [WinCap]::WindowsOf([uint32]$proc.Id)) {
  $r = New-Object WinCap+RECT
  if (-not [WinCap]::GetWindowRect($h, [ref]$r)) { continue }
  $w = $r.Right - $r.Left; $ht = $r.Bottom - $r.Top
  if ($w -le 0 -or $ht -le 0) { continue }
  $cands += [pscustomobject]@{
    Handle = $h; Left = $r.Left; Top = $r.Top; Width = $w; Height = $ht
    Visible = [WinCap]::IsWindowVisible($h); Iconic = [WinCap]::IsIconic($h)
    Area = $w * $ht; Title = [WinCap]::TitleOf($h)
  }
}

if (-not $cands) { Write-Error "no window found for $ProcessName"; exit 1 }
$cands | Sort-Object Area -Descending | Format-Table Handle, Left, Top, Width, Height, Visible, Iconic, Title -AutoSize | Out-String | Write-Host

# Prefer a titled window (the real frame) over untitled helper panes, then area.
# A minimized frame reports a tiny bogus rect, so restore it first without
# activating it, which keeps focus wherever the user had it.
$win = $cands | Sort-Object @{E={ if ($_.Title) { 0 } else { 1 } }}, @{E={$_.Area}; Descending=$true} |
       Select-Object -First 1
if ($win.Iconic) {
  Add-Type @"
using System; using System.Runtime.InteropServices;
public class WinShow { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); }
"@ -ErrorAction SilentlyContinue
  [void][WinShow]::ShowWindow($win.Handle, 4)   # SW_SHOWNOACTIVATE
  Start-Sleep -Milliseconds 700
  $r = New-Object WinCap+RECT
  [void][WinCap]::GetWindowRect($win.Handle, [ref]$r)
  $win.Left = $r.Left; $win.Top = $r.Top
  $win.Width = $r.Right - $r.Left; $win.Height = $r.Bottom - $r.Top
  Write-Host "restored (no activate) -> $($win.Width)x$($win.Height)"
}
Write-Host "chosen hwnd=$($win.Handle) $($win.Width)x$($win.Height) visible=$($win.Visible) iconic=$($win.Iconic) title='$($win.Title)'"

# 1) PrintWindow (works on occluded windows; flagged full-content)
foreach ($flag in 2, 0) {
  $bmp = New-Object System.Drawing.Bitmap($win.Width, $win.Height)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  $ok = [WinCap]::PrintWindow($win.Handle, $hdc, [uint32]$flag)
  $g.ReleaseHdc($hdc)
  $g.Dispose()
  $path = Join-Path $OutDir "$Tag-printwindow-$flag.png"
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Host "PrintWindow(flag=$flag) ok=$ok -> $path"
}

# 2) On-screen region copy (only meaningful when the window is visible on screen)
if ($win.Visible -and -not $win.Iconic) {
  $bmp = New-Object System.Drawing.Bitmap($win.Width, $win.Height)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($win.Left, $win.Top, 0, 0,
                    (New-Object System.Drawing.Size($win.Width, $win.Height)))
  $g.Dispose()
  $path = Join-Path $OutDir "$Tag-screen.png"
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Host "screen copy -> $path"
}
Write-Host 'done'
