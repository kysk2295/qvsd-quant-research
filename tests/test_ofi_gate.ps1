$text=Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot '../native/CodexQuoteOfi.cs')
$pure=($text -split '// BEGIN PURE OFI GATE')[1] -split '// END PURE OFI GATE' | Select-Object -First 1
Add-Type -TypeDefinition ('using System;'+$pure)
function Assert-Equal($actual,$expected,$name){if($actual -ne $expected){throw "$name expected $expected got $actual"}}
$now=[long]1800000000000000000;$end=$now-60000000000L;$last=$end-1
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,10,4,10)) 1 'Inclusive positive threshold and spread boundary'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,-10,1,10)) -1 'Negative OFI side'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,9.99,1,10)) 0 'Below threshold'
Assert-Equal ([CodexOfiGate]::Signal($now,$now,$last,$true,50,1,10)) 0 'Contemporaneous feature refused'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$end,$true,50,1,10)) 0 'Boundary event cannot enter prior feature'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$false,50,1,10)) 0 'Ineligible quotes'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,50,4.1,10)) 0 'Wide spread'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,50,0,10)) 0 'Locked quote'
Assert-Equal ([CodexOfiGate]::Signal($now,$end,$last,$true,[double]::NaN,1,10)) 0 'Nonfinite score'
Write-Output 'OFI decision gate passed9 boundary assertions against actual C# helper.'
