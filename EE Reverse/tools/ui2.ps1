# Interact with a top-level window by hwnd, optionally clicking first to bind the
# text caret, then sending mouse-wheel notches, then capturing the screen region.
# Coordinates are "shot" coordinates: relative to the window rect origin (-7,-7),
# which is the same origin the PrintWindow/BitBlt captures use.
param(
  [Parameter(Mandatory=$true)][string]$Hwnd,
  [int[]]$Click = @(),                 # e.g. -Click 900,420
  [int]$Ticks = 0,                     # positive = scroll down
  [int]$WheelAtX = 900,
  [int]$WheelAtY = 500,
  [string]$Out = ''
)
Add-Type -AssemblyName System.Drawing
$refs = @()
try { $refs += [System.Drawing.Bitmap].Assembly.Location } catch {}
Add-Type -ReferencedAssemblies $refs -TypeDefinition @"
using System; using System.Drawing; using System.Runtime.InteropServices;
public class UI2 {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public const uint LDOWN=0x0002, LUP=0x0004, WHEEL=0x0800;
  public static RECT Rect(long hwnd) {
    RECT r; GetWindowRect(new IntPtr(hwnd), out r); return r;
  }
  public static void Focus(long hwnd) {
    IntPtr h = new IntPtr(hwnd);
    ShowWindow(h, 9); SetForegroundWindow(h); System.Threading.Thread.Sleep(400);
  }
  public static string ClickAt(long hwnd, int sx, int sy) {
    RECT r = Rect(hwnd);
    int x = r.L + sx, y = r.T + sy;
    SetCursorPos(x, y); System.Threading.Thread.Sleep(150);
    mouse_event(LDOWN, 0, 0, 0, IntPtr.Zero);
    System.Threading.Thread.Sleep(60);
    mouse_event(LUP, 0, 0, 0, IntPtr.Zero);
    System.Threading.Thread.Sleep(300);
    return "clicked (" + x + "," + y + ")";
  }
  public static string Wheel(long hwnd, int notches, int sx, int sy) {
    RECT r = Rect(hwnd);
    SetCursorPos(r.L + sx, r.T + sy); System.Threading.Thread.Sleep(150);
    int n = notches < 0 ? -notches : notches;
    uint d = notches < 0 ? (uint)4294967176 : (uint)120;
    for (int i = 0; i < n; i++) {
      mouse_event(WHEEL, 0, 0, d, IntPtr.Zero);
      System.Threading.Thread.Sleep(90);
    }
    System.Threading.Thread.Sleep(300);
    return "wheel " + notches;
  }
  public static string Shoot(long hwnd, string path) {
    RECT r = Rect(hwnd);
    int w = r.R - r.L, ht = r.B - r.T;
    if (w <= 0 || ht <= 0) return "bad rect";
    var bmp = new Bitmap(w, ht);
    using (var g = Graphics.FromImage(bmp))
      g.CopyFromScreen(r.L, r.T, 0, 0, new Size(w, ht), CopyPixelOperation.SourceCopy);
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png);
    bmp.Dispose();
    return "shot " + w + "x" + ht;
  }
}
"@
$h = [Convert]::ToInt64($Hwnd, 16)
[UI2]::Focus($h) | Out-Null
$log = @()
if ($Click.Count -eq 2) { $log += [UI2]::ClickAt($h, $Click[0], $Click[1]) }
if ($Ticks -ne 0)        { $log += [UI2]::Wheel($h, $Ticks, $WheelAtX, $WheelAtY) }
if ($Out -ne '')         { $log += [UI2]::Shoot($h, $Out) }
$log -join '; '
