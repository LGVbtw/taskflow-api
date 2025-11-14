param(
    [int]$Count = 10,
    [string]$Url = 'http://127.0.0.1:8000/api/tasks/',
    [string]$CurlExe = 'curl.exe'
)

if (-not (Get-Command $CurlExe -ErrorAction SilentlyContinue)) {
    Write-Error "curl.exe introuvable. Assurez-vous que curl est installé et dans le PATH."
    exit 2
}

$times = @()
for ($i=1; $i -le $Count; $i++) {
    $out = & $CurlExe -s -o NUL -w "GET /api/tasks/ -> code:%{http_code} total:%{time_total}s`n" $Url
    # Extrait le time_total depuis la sortie (format connu)
    Write-Output $out.TrimEnd()
    if ($out -match 'total:([0-9.]+)s') {
        $t = [double]$Matches[1]
        $times += $t
    }
}

if ($times.Count -eq 0) {
    Write-Output "Aucun temps collecté."
    exit 0
}

$avg = ($times | Measure-Object -Average).Average
Write-Output "Moyenne sur $($times.Count) requêtes: {0:N6}s" -f $avg
