# 🚀 PyPI Upload Instructions

## Pre-Upload Checklist

- [x] Build completato con successo
- [x] twine check PASSED
- [x] Nessun warning di deprecazione
- [x] pyproject.toml aggiornato
- [x] Versione: 0.1.0
- [x] File generati:
  - telegram_menu_builder-0.1.0-py3-none-any.whl
  - telegram_menu_builder-0.1.0.tar.gz

## Configurazione ~/.pypirc

Devi avere il file `~/.pypirc` configurato con le tue credenziali PyPI:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Sostituisci con il tuo token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Token testpypi
```

## Comandi di Upload

### Step 1: TestPyPI (Opzionale ma Consigliato)

```bash
twine upload --repository testpypi dist/*
```

### Step 2: PyPI (Produzione)

```bash
twine upload dist/*
```

## Post-Upload

### Verificare su PyPI

https://pypi.org/project/telegram-menu-builder/

### Installare dal PyPI

```bash
pip install telegram-menu-builder
```

### Verificare l'importazione

```bash
python -c "import telegram_menu_builder; print(telegram_menu_builder.__version__)"
```

## Troubleshooting

### Error: HTTPError 403

Significa che l'account PyPI non è configurato correttamente. Verifica:
1. Username è `__token__`
2. Password è il token completo (inizia con `pypi-`)
3. Token ha permessi sufficienti

### Error: File already exists

Se ricarichi la stessa versione, PyPI rifiuterà il file. Devi:
1. Incrementare la versione in pyproject.toml
2. Rifare il build
3. Rifare l'upload

## Prossimi Step

Dopo il primo upload a PyPI:

1. ✅ Taggare il commit su GitHub
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```

2. ✅ Creare una GitHub Release

3. ✅ Aggiornare CHANGELOG.md

---

**Status**: Pronto per l'upload
