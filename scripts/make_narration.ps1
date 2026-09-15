param(
    [Parameter(Mandatory = $true)][string]$JsonPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$items = Get-Content -LiteralPath $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

foreach ($item in $items) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $synth.SelectVoice('Microsoft Huihui Desktop')
        $synth.Rate = -1
        $synth.Volume = 100
        $name = 'scene_{0:D2}.wav' -f [int]$item.index
        $target = Join-Path $OutputDirectory $name
        $synth.SetOutputToWaveFile($target)
        $synth.Speak([string]$item.text)
        $synth.SetOutputToNull()
        Write-Output "Created narration: $target"
    }
    finally {
        $synth.Dispose()
    }
}
