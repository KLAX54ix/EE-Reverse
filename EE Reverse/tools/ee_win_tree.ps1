# Enumerate the Editer window tree (children of the main frame AND all top-level
# windows of the same process, so floating panels like "函数曲线" are included).
#   powershell -File tools/ee_win_tree.ps1 -Hwnd 0x2a0012
param(
  [Parameter(Mandatory=$true)][string]$Hwnd
)
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WinTree {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static List<string> Rows = new List<string>();
  public static void Add(IntPtr h, string tag) {
    var cn = new StringBuilder(256); GetClassName(h, cn, 256);
    var tt = new StringBuilder(256); GetWindowText(h, tt, 256);
    RECT r; GetWindowRect(h, out r);
    Rows.Add(string.Format("{0} hwnd=0x{1:x} vis={2} class='{3}' title='{4}' rect=({5},{6},{7},{8})",
      tag, h.ToInt64(), IsWindowVisible(h) ? 1 : 0, cn, tt, r.L, r.T, r.R, r.B));
  }
  public static IntPtr Target;
  public static List<string> Run(long hwnd) {
    Rows.Clear();
    IntPtr h = new IntPtr(hwnd);
    uint pid; GetWindowThreadProcessId(h, out pid);
    Add(h, "FRAME");
    EnumChildWindows(h, delegate(IntPtr c, IntPtr p) { Add(c, "CHILD"); return true; }, IntPtr.Zero);
    EnumWindows(delegate(IntPtr w, IntPtr p) {
      uint wp; GetWindowThreadProcessId(w, out wp);
      if (wp == pid && w != h) Add(w, "TOP");
      return true;
    }, IntPtr.Zero);
    return Rows;
  }
}
"@
$h = [IntPtr][Convert]::ToInt64($Hwnd, 16)
$rows = [WinTree]::Run($h.ToInt64())
$rows | ForEach-Object { Write-Output $_ }
