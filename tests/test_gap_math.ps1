$text = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot '../native/CodexGapFade.cs')
$pure = ($text -split '// BEGIN PURE GAP MATH')[1] -split '// END PURE GAP MATH' | Select-Object -First 1
Add-Type -TypeDefinition ('using System;' + $pure)
function Assert-Equal($actual,$expected,$name) { if($actual -ne $expected) {throw "$name expected $expected, got $actual"} }
Assert-Equal ([CodexGapMath]::PreviousWeekday([datetime]'2026-10-12')) ([datetime]'2026-10-09') 'Monday context is Friday'
Assert-Equal ([CodexGapMath]::PreviousWeekday([datetime]'2026-10-08')) ([datetime]'2026-10-07') 'Weekday context'
Assert-Equal ([CodexGapMath]::Qualifies(970,1000,10,3)) $false 'Strict threshold equality'
Assert-Equal ([CodexGapMath]::Qualifies(969.75,1000,10,3)) $true 'One tick beyond threshold'
Assert-Equal ([CodexGapMath]::Qualifies(1031,1000,10,3)) $false 'Gap up is not long'
Assert-Equal ([CodexGapMath]::Qualifies(900,1000,0,3)) $false 'Zero volatility'
Assert-Equal ([CodexGapMath]::Qualifies(900,1000,[double]::NaN,3)) $false 'NaN volatility'
Assert-Equal ([CodexGapMath]::Qualifies(900,1000,[double]::PositiveInfinity,3)) $false 'Infinite volatility'
$values=[double[]](0..59 | ForEach-Object { if($_ % 2){11}else{9} })
if([Math]::Abs([CodexGapMath]::Sigma($values)-1) -gt 1e-10){throw 'Population sigma calculation'}
$failed=$false
try {$null=[CodexGapMath]::Sigma([double[]](1,2,3))}catch{$failed=$true}
Assert-Equal $failed $true 'Incomplete window rejected'
Write-Output 'Gap math boundary checks passed (10 assertions against actual C# helper).'
