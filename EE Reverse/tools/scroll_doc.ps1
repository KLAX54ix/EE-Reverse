param(
  [int]$ShotX = 1100,
  [int]$ShotY = 500,
  [int]$Notches = 5      # positive = scroll down
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class S {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public const uint WHEEL = 0x0800;
}
"@
$p = Get-Process Editer -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output 'no Editer window'; exit 1 }
$h = $p.MainWindowHandle
if ([S]::IsIconic($h)) { [S]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
[S]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 350
$wr = New-Object S+RECT; [S]::GetWindowRect($h, [ref]$wr) | Out-Null
$sx = $wr.L + $ShotX; $sy = $wr.T + $ShotY
[S]::SetCursorPos($sx, $sy) | Out-Null
Start-Sleep -Milliseconds 120
for ($i = 0; $i -lt [Math]::Abs($Notches); $i++) {
  # MOUSEEVENTF_WHEEL takes an unsigned delta; -120 is 0xFFFFFF88.
  $d = if ($Notches -lt 0) { [uint32]4294967176 } else { [uint32]120 }
  [S]::mouse_event([S]::WHEEL, 0, 0, $d, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 90
}
Start-Sleep -Milliseconds 250
Write-Output ("scrolled {0} notches at ({1},{2})" -f $Notches, $sx, $sy)
