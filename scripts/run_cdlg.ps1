param(
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$RuntimeDirectory
)
Set-Location -LiteralPath $RuntimeDirectory
& $PythonExecutable "generate_collection_of_logs.py"
exit $LASTEXITCODE
