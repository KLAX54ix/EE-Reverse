# Capture a top-level window by hwnd via PrintWindow (no Get-Process dependency).
param(
  [Parameter(Mandatory=$true)][string]$Hwnd,
  [Parameter(Mandatory=$true)][string]$Out
)
Add-Type -AssemblyName System.Drawing
$refs = @()
try { $refs += [System.Drawing.Bitmap].Assembly.Location } catch {}
try { $refs += [System.Drawing.Imaging.ImageFormat].Assembly.Location } catch {}
Add-Type -ReferencedAssemblies $refs -TypeDefinition @"
using System; using System.Drawing; using System.Runtime.InteropServices;
public class Cap2 {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static string Shoot(long hwnd, string path) {
    IntPtr h = new IntPtr(hwnd);
    RECT r; if (!GetWindowRect(h, out r)) return "GetWindowRect failed";
    int w = r.R - r.L, ht = r.B - r.T;
    if (w <= 0 || ht <= 0) return "bad rect " + w + "x" + ht;
    var bmp = new Bitmap(w, ht);
    using (var g = Graphics.FromImage(bmp)) {
      IntPtr dc = g.GetHdc();
      bool ok = PrintWindow(h, dc, 2);
      g.ReleaseHdc(dc);
      if (!ok) { PrintWindow(h, dc = g.GetHdc(), 0); g.ReleaseHdc(dc); }
    }
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png);
    bmp.Dispose();
    return "ok " + w + "x" + ht;
  }
}
"@
$res = [Cap2]::Shoot([Convert]::ToInt64($Hwnd, 16), $Out)
Write-Output $res
