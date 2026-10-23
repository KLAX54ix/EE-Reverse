# Crop-capture the physical screen region of a window (BitBlt from the screen DC).
# Unlike PrintWindow this cannot return a stale/blank bitmap, but it needs the
# window to be unobscured and it may steal focus.
param(
  [Parameter(Mandatory=$true)][string]$Hwnd,
  [Parameter(Mandatory=$true)][string]$Out
)
Add-Type -AssemblyName System.Drawing
$refs = @()
try { $refs += [System.Drawing.Bitmap].Assembly.Location } catch {}
Add-Type -ReferencedAssemblies $refs -TypeDefinition @"
using System; using System.Drawing; using System.Runtime.InteropServices;
public class ScCap {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static string Shoot(long hwnd, string path) {
    IntPtr h = new IntPtr(hwnd);
    // EduEditer auto-minimises (IsIconic -> icons at -16000,-16000) when it is
    // backgrounded. A BitBlt of that rect yields a 157x25 sliver and no error,
    // so always restore + wait for a real rect first.
    for (int tries = 0; tries < 12; tries++) {
      if (IsIconic(h)) { ShowWindow(h, 9); System.Threading.Thread.Sleep(250); }
      RECT probe;
      GetWindowRect(h, out probe);
      if (probe.R - probe.L > 400) break;
      System.Threading.Thread.Sleep(250);
    }
    ShowWindow(h, 9);              // SW_RESTORE
    SetForegroundWindow(h);
    System.Threading.Thread.Sleep(500);
    RECT r; if (!GetWindowRect(h, out r)) return "GetWindowRect failed";
    int w = r.R - r.L, ht = r.B - r.T;
    if (w <= 0 || ht <= 0) return "bad rect";
    if (r.L < -1000 || r.T < -1000) return "window still off-screen at (" + r.L + "," + r.T + ")";
    var bmp = new Bitmap(w, ht);
    using (var g = Graphics.FromImage(bmp)) {
      g.CopyFromScreen(r.L, r.T, 0, 0, new Size(w, ht), CopyPixelOperation.SourceCopy);
    }
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png);
    bmp.Dispose();
    return "ok " + w + "x" + ht + " at (" + r.L + "," + r.T + ")";
  }
}
"@
$res = [ScCap]::Shoot([Convert]::ToInt64($Hwnd, 16), $Out)
Write-Output $res
