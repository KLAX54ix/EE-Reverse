# Capture the whole (virtual) screen to a PNG. Used to see EE panels that float
# outside the main frame and therefore are cut off by a frame-only crop.
param(
  [string]$Out = 'D:\EE Reverse\captures\screen.png'
)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output ("ok {0}x{1} -> {2}" -f $b.Width, $b.Height, $Out)
