$source=Get-Content "$PSScriptRoot/../native/CodexMacdCross.cs" -Raw
$part=[regex]::Match($source,'(?s)// BEGIN PURE MACD MATH(.*?)// END PURE MACD MATH').Groups[1].Value
Add-Type -TypeDefinition ("using System; "+$part)
function Check($ok,$message) { if (!$ok) { throw $message } }
$seed=[CodexMacdMath]::Step(100,50,40,30,$true)
Check ($seed[0] -eq 100 -and $seed[1] -eq 100 -and $seed[2] -eq 0 -and $seed[3] -eq 0) 'RTH reset ignores prior session'
$up=[CodexMacdMath]::Step(110,100,100,0,$false)
Check ([Math]::Abs($up[0]-(100+20.0/13)) -lt 1e-12) 'fast EMA'
Check ([Math]::Abs($up[1]-(100+20.0/27)) -lt 1e-12) 'slow EMA'
Check ([Math]::Abs($up[3]-(20.0/13-20.0/27)*0.8) -lt 1e-12) 'signal EMA/histogram'
Check ([CodexMacdMath]::Cross(0,1) -eq 1) 'zero-to-positive'
Check ([CodexMacdMath]::Cross(0,-1) -eq -1) 'zero-to-negative'
Check ([CodexMacdMath]::Cross(-1,0) -eq 0) 'current zero no long'
Check ([CodexMacdMath]::Cross(1,0) -eq 0) 'current zero no short'
Check ([CodexMacdMath]::Cross(1,2) -eq 0) 'same sign no cross'
Write-Output 'Actual MACD C# math passed9 assertions'
