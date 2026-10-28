param([ValidateSet('voices','speak')][string]$Mode = 'voices')
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $voices = @($synth.GetInstalledVoices() | Where-Object Enabled | ForEach-Object {
    [pscustomobject]@{ name = $_.VoiceInfo.Name; language = $_.VoiceInfo.Culture.Name; gender = $_.VoiceInfo.Gender.ToString() }
  })
  if ($Mode -eq 'voices') { ConvertTo-Json -InputObject $voices -Compress; exit }
  $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
  if (-not $request.text -or $request.text.Length -gt 900) { throw 'Text must contain 1–900 characters.' }
  $language = [string]$request.language
  $voice = $voices | Where-Object { $_.language.Split('-')[0] -eq $language } | Sort-Object @{Expression={ if ($_.gender -eq 'Female') { 0 } else { 1 } }} | Select-Object -First 1
  if (-not $voice) { throw 'No installed offline voice supports this language.' }
  $synth.SelectVoice($voice.name)
  $synth.Rate = -1
  $synth.Volume = 90
  $buffer = New-Object System.IO.MemoryStream
  $synth.SetOutputToWaveStream($buffer)
  $synth.Speak([string]$request.text)
  $synth.SetOutputToNull()
  $bytes = $buffer.ToArray()
  ConvertTo-Json -Compress -InputObject @{ voice = $voice.name; language = $voice.language; audio = [Convert]::ToBase64String($bytes) }
  $buffer.Dispose()
} finally { $synth.Dispose() }
