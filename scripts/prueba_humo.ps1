# Prueba de humo de punta a punta contra la API (Windows PowerShell 5.1 o PowerShell 7).
# Recorre el flujo completo del operador y borra al final el analisis que crea.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1 -Url http://localhost:8080
#
# No modifica la configuracion de rangos. Aun asi, ejecutela en modo LOCAL: en modo nube
# crea (y luego borra) un analisis en la base compartida.
param(
    [string]$Url = "http://localhost"
)

$ErrorActionPreference = "Stop"
$api = "$Url/api"
$temporal = Join-Path ([System.IO.Path]::GetTempPath()) ("prueba_humo_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporal | Out-Null
$fallas = 0

function Write-Paso([string]$nombre, [bool]$ok, [string]$detalle = "") {
    if ($ok) { Write-Host "[PASA]  $nombre $detalle" -ForegroundColor Green }
    else { Write-Host "[FALLA] $nombre $detalle" -ForegroundColor Red; $script:fallas++ }
}

# Llama a la API con curl.exe y devuelve @{ Codigo = <int>; Cuerpo = <texto> }.
function Invoke-Api([string]$metodo, [string]$ruta, [string]$json = "", [string[]]$extra = @()) {
    $salida = Join-Path $temporal "respuesta.txt"
    $argumentos = @("-s", "-o", $salida, "-w", "%{http_code}", "-X", $metodo, "$api$ruta")
    if ($json) {
        $archivo = Join-Path $temporal "cuerpo.json"
        [System.IO.File]::WriteAllText($archivo, $json)
        $argumentos += @("-H", "Content-Type: application/json", "--data-binary", "@$archivo")
    }
    $argumentos += $extra
    $codigo = [int](& curl.exe @argumentos)
    $cuerpo = if (Test-Path $salida) { [System.IO.File]::ReadAllText($salida) } else { "" }
    return @{ Codigo = $codigo; Cuerpo = $cuerpo }
}

function New-ImagenPrueba([string]$ruta) {
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap 1600, 1200
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(200, 195, 185))
    $pincel = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(90, 88, 85))
    foreach ($i in 0..9) { $g.FillEllipse($pincel, 100 + $i * 140, 400, 60 + $i * 8, 50 + $i * 6) }
    $g.Dispose()
    $bmp.Save($ruta, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $bmp.Dispose()
}

function Get-Cuadrado([double]$x, [double]$y, [double]$lado) {
    return "[{`"x`":$x,`"y`":$y},{`"x`":$($x+$lado),`"y`":$y},{`"x`":$($x+$lado),`"y`":$($y+$lado)},{`"x`":$x,`"y`":$($y+$lado)}]"
}

try {
    Write-Host "Prueba de humo contra $api`n"

    # 1. Salud y modelo
    $r = Invoke-Api "GET" "/salud"
    $salud = $r.Cuerpo | ConvertFrom-Json
    Write-Paso "GET /salud" ($r.Codigo -eq 200 -and $salud.estado -eq "ok") "(modelo_disponible=$($salud.modelo_disponible))"

    # 2. Crear analisis (RF-01) y rechazo de formato no valido
    $imagen = Join-Path $temporal "pila.jpg"
    New-ImagenPrueba $imagen
    $r = Invoke-Api "POST" "/analisis" "" @("-F", "nombre=prueba-humo", "-F", "imagen=@$imagen")
    $id = ($r.Cuerpo | ConvertFrom-Json).id
    Write-Paso "POST /analisis (JPG)" ($r.Codigo -eq 201 -and $id) "(id=$id)"

    $texto = Join-Path $temporal "no_es_imagen.txt"
    [System.IO.File]::WriteAllText($texto, "hola")
    $r = Invoke-Api "POST" "/analisis" "" @("-F", "nombre=malo", "-F", "imagen=@$texto")
    Write-Paso "POST /analisis con .txt -> 415" ($r.Codigo -eq 415)

    # 3. No se puede segmentar sin calibrar (HU-02)
    $r = Invoke-Api "POST" "/analisis/$id/segmentacion"
    Write-Paso "Segmentar sin calibrar -> 409" ($r.Codigo -eq 409)

    # 4. Calibrar (RF-02): 500 px = 250 mm -> 0,5 mm/px
    $r = Invoke-Api "PUT" "/analisis/$id/calibracion" '{"inicio":{"x":0,"y":0},"fin":{"x":300,"y":400},"longitud_real_mm":250}'
    $factor = ($r.Cuerpo | ConvertFrom-Json).factor_mm_por_px
    Write-Paso "PUT /calibracion" ($r.Codigo -eq 200 -and $factor -eq 0.5) "(factor=$factor mm/px)"

    # 5. Region excluida (RF-03)
    $r = Invoke-Api "PUT" "/analisis/$id/region-excluida" ("{`"poligono`":" + (Get-Cuadrado 1400 1000 150) + "}")
    Write-Paso "PUT /region-excluida" ($r.Codigo -eq 200)

    # 6. Segmentacion automatica (RF-04): 200 con modelo, 503 sin modelo
    $r = Invoke-Api "POST" "/analisis/$id/segmentacion"
    if ($salud.modelo_disponible) {
        $n = (ConvertFrom-Json $r.Cuerpo).Count
        Write-Paso "POST /segmentacion (con modelo)" ($r.Codigo -eq 200) "($n fragmentos)"
    } else {
        Write-Paso "POST /segmentacion (sin modelo) -> 503" ($r.Codigo -eq 503)
    }

    # 7. Edicion manual (RF-05): 4 fragmentos + uno dentro de la region excluida (debe rechazarse)
    $fragmentos = @(
        (Get-Cuadrado 100 100 40), (Get-Cuadrado 200 100 80), (Get-Cuadrado 400 100 160), (Get-Cuadrado 700 100 60)
    ) | ForEach-Object { "{`"poligono`":$_}" }
    $r = Invoke-Api "PUT" "/analisis/$id/fragmentos" ("{`"fragmentos`":[" + ($fragmentos -join ",") + "]}")
    Write-Paso "PUT /fragmentos (4 manuales)" ($r.Codigo -eq 200 -and (ConvertFrom-Json $r.Cuerpo).Count -eq 4)

    $r = Invoke-Api "PUT" "/analisis/$id/fragmentos" ("{`"fragmentos`":[{`"poligono`":" + (Get-Cuadrado 1450 1050 20) + "}]}")
    Write-Paso "Fragmento en region excluida -> 422" ($r.Codigo -eq 422)

    # 8. Resultados (RF-06 a RF-08)
    $r = Invoke-Api "GET" "/analisis/$id/resultados"
    $res = $r.Cuerpo | ConvertFrom-Json
    $orden = $res.d20 -le $res.d50 -and $res.d50 -le $res.d60 -and $res.d60 -le $res.d80 -and $res.d80 -le $res.d90
    Write-Paso "GET /resultados" ($r.Codigo -eq 200 -and $orden -and $res.rangos.Count -ge 2) `
        ("(D50={0:N1} mm, D80={1:N1} mm, n={2:N2}, {3} rangos)" -f $res.d50, $res.d80, $res.indice_n, $res.rangos.Count)

    # 9. CSV (RF-09, RNF-07)
    $csv = Join-Path $temporal "resultados.csv"
    $r = Invoke-Api "GET" "/analisis/$id/resultados.csv"
    Copy-Item (Join-Path $temporal "respuesta.txt") $csv
    $lineas = Get-Content $csv -Encoding UTF8
    $okCsv = $r.Codigo -eq 200 -and ($lineas[0] -like "*Informe granulometrico;prueba-humo") -and ($lineas -match "^D50 \(mm\);").Count -eq 1
    Write-Paso "GET /resultados.csv" $okCsv "($($lineas.Count) lineas)"

    # 10. Reanudar (RF-10): el detalle conserva calibracion, region y poligonos
    $r = Invoke-Api "GET" "/analisis/$id"
    $det = $r.Cuerpo | ConvertFrom-Json
    $okDetalle = $det.estado -eq "SEGMENTADO" -and $det.calibracion -and $det.region_excluida -and $det.fragmentos.Count -eq 4
    Write-Paso "GET /analisis/{id} (reanudar)" $okDetalle

    # 11. Configuracion de rangos (RF-14), solo lectura
    $r = Invoke-Api "GET" "/configuracion/rangos"
    $cfg = $r.Cuerpo | ConvertFrom-Json
    Write-Paso "GET /configuracion/rangos" ($r.Codigo -eq 200 -and $cfg.colores.Count -eq ($cfg.cortes.Count + 1)) "(modo=$($cfg.modo))"

    # 12. Historial (RF-12) y limpieza
    $r = Invoke-Api "GET" "/analisis"
    Write-Paso "GET /analisis (historial)" ($r.Codigo -eq 200 -and ($r.Cuerpo | ConvertFrom-Json | Where-Object { $_.id -eq $id }))
    $r = Invoke-Api "DELETE" "/analisis/$id"
    Write-Paso "DELETE /analisis/{id}" ($r.Codigo -eq 204)
}
catch {
    Write-Paso "Ejecucion" $false $_.Exception.Message
}
finally {
    Remove-Item -Recurse -Force $temporal -ErrorAction SilentlyContinue
}

if ($fallas -eq 0) { Write-Host "`nTodo correcto." -ForegroundColor Green; exit 0 }
Write-Host "`n$fallas paso(s) fallaron." -ForegroundColor Red
exit 1
