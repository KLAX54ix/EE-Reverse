# Re-baseline verification for the EduEditer RE project (idempotent).
# Recomputes sha256/size of the 5 A-class targets, writes analysis\RE-BASELINE.json
# (single source of truth for the baseline) and prints a summary table.
# Exit code: 0 = ALL MATCH, 2 = mismatch or missing file.
param(
  [string]$Dir = 'D:\educationeditor\EduEditer',
  [string]$Out = 'D:\EE Reverse\analysis\RE-BASELINE.json'
)

$targets = @(
  [ordered]@{ id='T1'; name='Editer.exe'; class='A'; role='MFC main program (x86 UI/doc layer)';   size=5383168; sha256='3B12A439EB00DA965FB1232271683B653776D5BC54C8EC172F70DD20037EE2D8'; project='EEediter'; exports_dump=$null },
  [ordered]@{ id='T2'; name='eslib.dll';  class='A'; role='drawing/document engine (16123 exp)';  size=7273984; sha256='3AD0831A71FF921FEFEB7B3EF9845F2269B69A4A19FA5E0AABEFC7948C63FA0F'; project='EEeslib';  exports_dump='D:\EE Reverse\recon\eslib_exports.txt' },
  [ordered]@{ id='T3'; name='eulib.dll';  class='A'; role='MFC extension framework';               size=1065984; sha256='ECA35D2CBC7E7431D9953776BF260A77330249EC5EC8C3866E8B1DEFED37075E'; project=$null;     exports_dump='D:\EE Reverse\recon\eulib_exports.txt' },
  [ordered]@{ id='T4'; name='zoro.dll';   class='A'; role='base library (zArchive/zList/zwstr)';  size=284672;  sha256='1B06570B8DFA8E55065549FEADA3AB4B2950702B1D3793F0FD7801AD6CA15C22'; project=$null;     exports_dump='D:\EE Reverse\recon\zoro_exports.txt' },
  [ordered]@{ id='T5'; name='eglib.dll';  class='A'; role='GUI layer (eg_gui)';                   size=765952;  sha256='D826FCB77FCDEB2267BE12C3F6C8E1CAE86BACB51C9DA0EA0357EF92AB9C7EC0'; project=$null;     exports_dump='D:\EE Reverse\recon\eglib_exports.txt' }
)

$results = @()
$allMatch = $true
foreach ($t in $targets) {
  $path = Join-Path $Dir $t.name
  $rec = [ordered]@{
    id=$t.id; name=$t.name; class=$t.class; role=$t.role
    expect_size=$t.size; expect_sha256=$t.sha256
    path=$path; exists=$false; actual_size=$null; actual_sha256=$null
    size_match=$false; hash_match=$false
    ghidra_project=$t.project; exports_dump=$t.exports_dump; exports_lines=$null
  }
  if (Test-Path -LiteralPath $path) {
    $fi = Get-Item -LiteralPath $path
    $rec.exists = $true
    $rec.actual_size = $fi.Length
    $rec.actual_sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $rec.size_match = ([int64]$fi.Length -eq [int64]$t.size)
    $rec.hash_match = ($rec.actual_sha256 -eq $t.sha256)
  }
  if ($t.exports_dump -and (Test-Path -LiteralPath $t.exports_dump)) {
    $rec.exports_lines = (Get-Content -LiteralPath $t.exports_dump | Measure-Object -Line).Lines
  }
  if (-not ($rec.exists -and $rec.size_match -and $rec.hash_match)) { $allMatch = $false }
  $results += $rec
}

$doc = [ordered]@{
  schema         = 're-baseline/1'
  workspace      = 'D:\EE Reverse'
  created        = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
  invariant      = 'The 5 sha256 values above are the immutable analysis baseline. On mismatch: mark BASELINE-MISMATCH at the top of RE-STATUS.md, demote all existing conclusions to stale, and stop deep analysis until the user re-confirms a new baseline.'
  all_match      = $allMatch
  targets        = $results
  assets         = [ordered]@{
    recon_exports_dir = 'D:\EE Reverse\recon'
    ghidra_projects   = 'D:\EE Reverse\analysis\ghidra-proj (EEediter, EEeslib analyzed; EEeulib/EEzoro/EEeglib pending import)'
    epaddin_note      = 'EpAddin.dll is an OLE server add-in; tracked separately, not part of the 5-target baseline.'
  }
}
$json = $doc | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($Out, $json, (New-Object System.Text.UTF8Encoding($false)))

foreach ($r in $results) {
  $m = if ($r.hash_match -and $r.size_match) { 'MATCH' } else { 'MISMATCH' }
  $ln = if ($null -eq $r.exports_lines) { '-' } else { $r.exports_lines }
  Write-Output ("{0} {1,-12} size={2,-9} sha256={3} exports_lines={4,-6} -> {5}" -f `
    $r.id, $r.name, $r.actual_size, $r.actual_sha256, $ln, $m)
}
Write-Output ""
Write-Output ("ALL_MATCH = {0}" -f $allMatch)
Write-Output ("written: {0}" -f $Out)
if ($allMatch) { exit 0 } else { exit 2 }
