# 📋 Configurazione PyPI Token

Per pubblicare su PyPI, devi configurare il token di autenticazione.

## Step 1: Generare il Token su PyPI

1. Vai su https://pypi.org/account/
2. Login con il tuo account
3. Vai su "Account Settings" → "API tokens"
4. Clicca "Add API token"
5. Nomina il token (es: "telegram-menu-builder")
6. Salva il token completo (inizia con `pypi-`)

## Step 2: Configurare ~/.pypirc

Crea il file `%USERPROFILE%\.pypirc` con il seguente contenuto:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-[IL-TUO-TOKEN-QUI]

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-[IL-TUO-TESTPYPI-TOKEN-QUI]
```

### Su Windows

```powershell
# Creare il file
$content = @"
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-[IL-TUO-TOKEN]
"@

$filePath = "$env:USERPROFILE\.pypirc"
$content | Out-File -FilePath $filePath -Encoding ASCII
```

## Step 3: Verificare la Configurazione

```bash
twine upload --repository testpypi dist/*
```

Se funziona, sei pronto per il PyPI reale:

```bash
twine upload dist/*
```

## Alternativa: Upload Diretto con Token

Se non vuoi usare .pypirc, puoi anche fare:

```bash
twine upload dist/ -u __token__ -p pypi-[IL-TUO-TOKEN]
```

---

Una volta configurato, esegui il file `upload_to_pypi.sh` per automatizzare il processo.
