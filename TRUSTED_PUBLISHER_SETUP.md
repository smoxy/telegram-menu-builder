# 🔐 PyPI Trusted Publisher Setup Guide

## Che cos'è Trusted Publisher?

**Trusted Publisher** è un meccanismo di sicurezza moderno che usa **OpenID Connect (OIDC)** per pubblicare pacchetti su PyPI senza usare API token.

### Vantaggi

✅ **Non serve memorizzare token** - Niente credenziali da proteggere  
✅ **Automatico** - GitHub Actions crea automaticamente token temporanei  
✅ **Più sicuro** - Token scadono dopo il workflow  
✅ **Tracciabilità** - Ogni publish è tracciato a GitHub Actions  

---

## 📋 Configurazione Passo-Passo

### Step 1️⃣: Creare il Progetto su PyPI (se non esiste)

1. Vai su https://pypi.org/account/register/
2. Crea account (se non ce l'hai)
3. **Crea il progetto** facendo un upload manuale:
   ```bash
   twine upload dist/* -u __token__ -p pypi-[TOKEN]
   ```
   
   Oppure aspetta il primo workflow automatico.

### Step 2️⃣: Configurare Trusted Publisher su PyPI

1. **Login su PyPI**: https://pypi.org/account/login/

2. **Vai a Publishing**: https://pypi.org/manage/account/publishing/

3. **Clicca "Add a new pending publisher"**

4. **Compila il form:**

| Campo | Valore | Descrizione |
|-------|--------|-------------|
| **PyPI Project Name** | `telegram-menu-builder` | Nome esatto del progetto PyPI |
| **Owner** | `smoxy` | Il tuo username GitHub |
| **Repository name** | `telegram-menu-builder` | Nome repository su GitHub |
| **Workflow name** | `python-publish.yml` | Nome del file workflow (include `.yml`) |
| **Environment name** | `pypi` | Nome ambiente GitHub Actions (vedi sotto) |

5. **Clicca "Add"**

✅ Trusted Publisher è configurato!

---

## 🔧 Configurazione GitHub Repository

### Step 3️⃣: Creare Environment su GitHub

1. Vai al repository: https://github.com/smoxy/telegram-menu-builder

2. **Vai a Settings** → **Environments**

3. **Clicca "New environment"**

4. Nomina l'environment: `pypi`

5. **Clicca "Configure environment"**

6. **Aggiungi Protection Rules (Opzionale ma Consigliato)**
   - ✅ "Require reviewers" - Richiede review prima di publish
   - Aggiungi te stesso come reviewer

7. **Clicca "Save protection rules"**

### Step 4️⃣: Verificare il Workflow

Il file `.github/workflows/python-publish.yml` è già stato creato con:

- ✅ Tests (pytest, mypy, pyright, ruff)
- ✅ Build (wheel + sdist)
- ✅ Verify (twine check)
- ✅ Publish (OIDC trusted publishing)

---

## 🚀 Come Publicare una Nuova Versione

### Procedura Standard

1. **Aggiorna la versione** in `pyproject.toml`:
   ```toml
   [project]
   version = "0.2.0"  # Incrementa il numero
   ```

2. **Aggiorna CHANGELOG.md** con i cambiamenti

3. **Commit e push**:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "bump: version 0.2.0"
   git push origin main
   ```

4. **Crea un Release su GitHub**:
   - Vai a https://github.com/smoxy/telegram-menu-builder/releases
   - Clicca "Create a new release"
   - **Tag version**: `v0.2.0`
   - **Release title**: `Release v0.2.0`
   - **Description**: Copia da CHANGELOG
   - Clicca "Publish release"

5. **Automatic Workflow Runs**:
   - ✅ GitHub Actions legge il release
   - ✅ Esegue tutti i tests
   - ✅ Se tutto passa → Build
   - ✅ Se build passa → Publish automaticamente su PyPI
   - ✅ Vedi il progetto su https://pypi.org/project/telegram-menu-builder/

---

## 🔍 Monitorare il Workflow

1. **Durante il processo**:
   - Vai a: https://github.com/smoxy/telegram-menu-builder/actions
   - Vedi il workflow "Publish to PyPI" in esecuzione

2. **Controlli durante il workflow**:
   ```
   ✓ Tests (pytest, mypy, pyright, ruff)
   ✓ Build (python -m build)
   ✓ Verify (twine check)
   ✓ Publish (GitHub OIDC token)
   ```

3. **Se fallisce un test**:
   - ❌ Workflow si ferma
   - ❌ Nessun publish
   - ✅ Devi fixare il bug e ricreare il release

---

## ⚙️ Configurazione Avanzata

### Aggiungere Test Matrix (Multipli Python)

Se vuoi testare su Python 3.12 e 3.13:

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
```

### Aggiungere Linting Pre-Publish

Il workflow include già:
- ✅ pytest
- ✅ mypy
- ✅ pyright  
- ✅ ruff

### Coverage Report

Aggiungi a workflow (opzionale):

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

---

## 🔐 Sicurezza - Best Practices

✅ **Non usare password** - Solo Trusted Publisher  
✅ **No API tokens nel code** - Usa OIDC  
✅ **Environment protection** - Review prima di publish  
✅ **Test obbligatori** - Niente passa senza test  
✅ **Signed commits** - (opzionale) Firma i tuoi commits  

---

## 📚 Risoluzione Problemi

### Problema: "Trusted Publisher not found"

**Soluzione**: 
- Verifica che PyPI Project Name sia esatto: `telegram-menu-builder`
- Verifica che il repository esista
- Aspetta 5 minuti per la propagazione

### Problema: "Workflow non corre al release"

**Soluzione**:
- Verifica che il workflow file sia in `.github/workflows/python-publish.yml`
- Il nome del workflow deve essere `on: release`
- Deve essere sulla branch `main`

### Problema: "Tests falliscono"

**Soluzione**:
- Fix il codice localmente
- Fai commit e push
- Riprova il release

---

## ✨ Vantaggi della Configurazione

| Aspetto | Prima | Dopo |
|--------|-------|------|
| **Autenticazione** | Token nel file .pypirc | OIDC automatico |
| **Manualità** | `twine upload` manuale | Automatico su release |
| **Sicurezza** | Token persistente | Token temporaneo |
| **Tracciabilità** | Solo upload | Tests + Build + Publish |
| **Affidabilità** | Errori manuali | 0% errori umani |

---

## 🎯 Prossimi Step

1. ✅ Workflow creato: `.github/workflows/python-publish.yml`
2. ⏳ Configura Trusted Publisher su PyPI (form a https://pypi.org/manage/account/publishing/)
3. ⏳ Crea environment `pypi` su GitHub (Settings → Environments)
4. ✅ Pronto per il primo release automatico!

---

## 📞 Help

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **PyPI Trusted Publishers**: https://docs.pypi.org/trusted-publishers/
- **OIDC Support**: https://docs.github.com/en/actions/deployment/about-deployments/using-openid-connect-with-reusable-workflows

