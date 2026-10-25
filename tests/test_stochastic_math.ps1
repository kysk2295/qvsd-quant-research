$source=Get-Content "$PSScriptRoot/../native/CodexStochasticFast.cs" -Raw
$part=[regex]::Match($source,'(?s)// BEGIN PURE STOCH MATH(.*?)// END PURE STOCH MATH').Groups[1].Value
Add-Type -TypeDefinition ("using System; "+$part)
function Check($ok,$message) { if (!$ok) { throw $message } }
Check ([CodexStochMath]::Raw(10,10,0) -eq 100) 'window high'
Check ([CodexStochMath]::Raw(0,10,0) -eq 0) 'window low'
Check ([CodexStochMath]::Raw(5,10,0) -eq 50) 'midpoint'
Check ([double]::IsNaN([CodexStochMath]::Raw(10,10,10))) 'zero width invalid'
Check ([CodexStochMath]::Cross(10,11,15,12) -eq 1) 'oversold upcross'
Check ([CodexStochMath]::Cross(90,89,85,88) -eq -1) 'overbought downcross'
Check ([CodexStochMath]::Cross(10,11,20,12) -eq 0) 'strict20 boundary'
Check ([CodexStochMath]::Cross(90,89,80,88) -eq 0) 'strict80 boundary'
Check ([CodexStochMath]::Cross(10,10,15,12) -eq 1) 'previous equality counts'
Check ([CodexStochMath]::Cross(10,11,12,12) -eq 0) 'current equality not crossing'
Check ([CodexStochMath]::Cross([double]::NaN,11,15,12) -eq 0) 'incomplete prior context'
Write-Output 'Actual native stochastic math passed11boundary checks'
