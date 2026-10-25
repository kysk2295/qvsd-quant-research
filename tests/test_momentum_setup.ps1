$sourceFile = Join-Path $PSScriptRoot '../native/CodexMovingMomentum.cs'
$sourceText = Get-Content -Raw -LiteralPath $sourceFile
$pure = ($sourceText -split '// BEGIN PURE SETUP STATE: tested directly without NinjaTrader or market access.')[1] -split '// END PURE SETUP STATE' | Select-Object -First 1
Add-Type -TypeDefinition $pure
function Assert-Equal($actual, $expected, $caseName) {
    if ($actual -ne $expected) { throw "$caseName expected $expected, observed $actual" }
}
$state = [CodexMomentumSetupState]::new()
Assert-Equal ($state.Step(1,10,1,-1,100,6)) 0 'No same-bar confirmation'
Assert-Equal ($state.Step(1,30,2,1,101,6)) 0 'Positive sign alone is insufficient'
Assert-Equal ($state.Step(1,30,1,-1,102,6)) 1 'Ordered long confirmation'
Assert-Equal $state.SignalAge 2 'Setup age'
Assert-Equal ($state.Step(1,30,1,-1,103,6)) 0 'Consumed setup cannot duplicate'
$state.Clear()
Assert-Equal ($state.Step(-1,90,1,2,200,6)) 0 'Short armed'
Assert-Equal ($state.Step(-1,50,-1,1,206,6)) -1 'Sixth bar is inclusive'
$state.Clear()
$null = $state.Step(1,10,-1,-2,300,6)
Assert-Equal ($state.Step(1,10,-2,-1,305,6)) 0 'Repeated extreme does not refresh'
Assert-Equal ($state.Step(1,30,1,-1,307,6)) 0 'Seventh bar expires'
Assert-Equal $state.Event 'setup_expired' 'Expiry event'
$null = $state.Step(1,10,-1,-2,400,6)
Assert-Equal ($state.Step(-1,90,-1,1,401,6)) 0 'Bias change invalidates before opposite confirmation'
Assert-Equal $state.Side 0 'Invalidation clears setup'
$null = $state.Step(1,10,-1,-2,500,6)
$state.Clear()
Assert-Equal ($state.Step(1,30,1,-1,501,6)) 0 'Session reset clears setup'
Write-Output 'Momentum setup boundary checks passed (13 assertions against actual C# helper).'
