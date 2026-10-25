$source = Get-Content "$PSScriptRoot/../native/CodexBollingerReturn.cs" -Raw
$part = [regex]::Match($source, '(?s)// BEGIN PURE BAND MATH(.*?)// END PURE BAND MATH').Groups[1].Value
Add-Type -TypeDefinition ("using System; using System.Linq; " + $part)
function Check($ok,$message) { if (!$ok) { throw $message } }
$bands=[CodexBandMath]::Bands([double[]](1..20))
Check ([Math]::Abs($bands[0]-10.5) -lt 1e-12) 'mean'
Check ([Math]::Abs($bands[1]-(10.5-2*[Math]::Sqrt(33.25))) -lt 1e-12) 'population sigma'
Check ([CodexBandMath]::Signal(5,5,15,6,5,15) -eq 1) 'prior equality allows long'
Check ([CodexBandMath]::Signal(4,5,15,5,5,15) -eq 0) 'current equality is not crossing'
Check ([CodexBandMath]::Signal(15,5,15,14,5,15) -eq -1) 'prior equality allows short'
Check ([CodexBandMath]::Signal(16,5,15,15,5,15) -eq 0) 'short equality excluded'
Check ([CodexBandMath]::Signal(10,5,15,11,5,15) -eq 0) 'inside bands no entry'
$flat=[CodexBandMath]::Bands([double[]](@(100)*20))
Check ($flat[0] -eq 100 -and $flat[1] -eq 100 -and $flat[2] -eq 100) 'constant series'
Write-Output 'Actual C# band math passed8 assertions'
