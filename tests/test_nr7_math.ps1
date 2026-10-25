$source=Get-Content "$PSScriptRoot/../native/CodexNr7Rth.cs" -Raw
$part=[regex]::Match($source,'(?s)// BEGIN PURE NR7 MATH(.*?)// END PURE NR7 MATH').Groups[1].Value
Add-Type -TypeDefinition ("using System; using System.Linq; "+$part)
function Check($ok,$message) { if (!$ok) { throw $message } }
Check ([CodexNr7Math]::Qualifies([double[]]@(7,6,5,4,3,2,1))) 'strict narrowest'
Check (![CodexNr7Math]::Qualifies([double[]]@(7,6,5,4,3,2,2))) 'ties excluded'
Check (![CodexNr7Math]::Qualifies([double[]]@(6,5,4,3,2,1))) 'six sessions insufficient'
Check (![CodexNr7Math]::Qualifies([double[]]@(7,6,5,4,3,2,0))) 'zero range rejected'
Check (![CodexNr7Math]::Qualifies([double[]]@(1,2,3,4,5,6,7))) 'wrong chronological direction'
Check (![CodexNr7Math]::Qualifies([double[]]@(7,6,5,4,3,2,[double]::NaN))) 'NaN rejected'
Check ([CodexNr7Math]::Breakout(110,110,100) -eq 0) 'touch not breakout'
Check ([CodexNr7Math]::Breakout(110.25,110,100) -eq 1) 'one tick above'
Check ([CodexNr7Math]::Breakout(99.75,110,100) -eq -1) 'one tick below'
Check ([CodexNr7Math]::PreviousWeekday([datetime]'2026-10-12') -eq [datetime]'2026-10-09') 'Monday context'
Write-Output 'Actual NR7 daily math passed10 boundary assertions'
