$ErrorActionPreference = "Stop"

python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

git diff --check
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

git status --short
