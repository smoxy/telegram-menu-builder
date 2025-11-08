# 📦 PyPI Publishing Guide - Best Practices

## Pre-requisiti

### 1. Account PyPI
- ✅ Registrato su https://pypi.org
- ✅ Username: `smoxy`
- ✅ Token API generato e salvato in `~/.pypirc`

### 2. Tools Necessari
```bash
pip install --upgrade pip setuptools wheel twine build
```

## Step-by-Step Publishing

### Step 1: Verifica Configurazione Locale ✅
- [x] pyproject.toml corretto
- [x] version: 0.1.0
- [x] name: telegram-menu-builder
- [x] Metadati completi
- [x] LICENSE presente

### Step 2: Test di Build ✅
```bash
python -m build
```

### Step 3: Verifica Distribuzione ✅
```bash
twine check dist/*
```

### Step 4: Upload a TestPyPI (Opzionale ma Consigliato)
```bash
twine upload --repository testpypi dist/*
```

### Step 5: Upload a PyPI (Produzione)
```bash
twine upload dist/*
```

## Checklist Pre-Pubblicazione

- [ ] Versione incrementata in pyproject.toml
- [ ] CHANGELOG.md aggiornato
- [ ] README.md completo
- [ ] LICENSE presente e valido
- [ ] Nessun file sensibile in dist/
- [ ] Tests passano (pytest)
- [ ] Type checks passano (mypy, pyright)
- [ ] Commit e tag creato in git
- [ ] Nessuna warningsdell build

## Configurazione PyPI (.pypirc)

Il file `~/.pypirc` deve contenere:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgE...

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgE...
```

## Post-Pubblicazione

1. ✅ Verificare su PyPI: https://pypi.org/project/telegram-menu-builder/
2. ✅ Testare l'installazione: `pip install telegram-menu-builder`
3. ✅ Aggiornare CHANGELOG
4. ✅ Taggare release su GitHub
5. ✅ Creare GitHub Release

## Versioning Strategy (Semantic Versioning)

```
MAJOR.MINOR.PATCH
0.1.0

- MAJOR: Cambio incompatibile con versioni precedenti
- MINOR: Nuove features mantenendo compatibilità
- PATCH: Bug fix
```

## Comandi Utili

```bash
# Build
python -m build

# Verifica
twine check dist/*

# Upload su TestPyPI
twine upload --repository testpypi dist/*

# Upload su PyPI
twine upload dist/*

# Installazione locale per test
pip install -e .

# Installazione da PyPI
pip install telegram-menu-builder

# Verifica versione
python -c "import telegram_menu_builder; print(telegram_menu_builder.__version__)"
```

---

**Status**: Pronto per la pubblicazione
