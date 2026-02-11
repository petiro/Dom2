# 🚀 SuperAgent V4 Pro: Autonomous Betting Enterprise

SuperAgent V4 Pro è un framework di automazione d'élite per il betting ad alta frequenza. Non è un semplice bot, ma un **Agente Autonomo Ridondante** che integra Intelligenza Artificiale multi-modello, navigazione stealth avanzata (Playwright) e un'architettura self-healing progettata per operare **24/7 senza supervisione umana**.

---

## 💎 Caratteristiche d'Élite

### 🧠 1. AI Fallback Chain (5 Livelli di Resilienza)

Il sistema garantisce il mapping del DOM e la logica decisionale anche in caso di outage delle API primarie, scalando automaticamente attraverso:

- **Anthropic Claude 3.5 Sonnet**: Motore logico primario per precisione chirurgica.
- **GPT-OSS-120b**: Fallback ad alte prestazioni.
- **Qwen 3 Coder 480b**: Specialista nell'analisi di strutture HTML complesse.
- **Gemini 2.0 Flash Lite**: Velocità estrema per decisioni real-time.
- **Arcee-AI Trinity**: L'ultima linea di difesa per la continuità operativa.

### 🛡️ 2. Architettura Sentinel & Guardian

Il cuore del sistema è protetto da tre layer di supervisione:

- **Sentinel Core**: Monitora la latenza e attiva l'Hot-Swap tra istanze parallele di Chrome se rileva anomalie.
- **Guardian Core**: Previene il "suicidio" del bot monitorando loop infiniti e streak di fallimenti.
- **Autonomous Healer**: Ripara automaticamente la connessione CDP e ricicla il browser in caso di memory leak o freeze.

### 🔌 3. Bet365.it Real-Time Bridge

Integrazione nativa e profonda per Bet365.it:

- **Stealth Tracking**: Movimenti del mouse basati su curve di Bezier umane e digitazione dinamica.
- **DOM Monitoring**: Rilevamento istantaneo di cambi quota e mercati sospesi.
- **Anti-Bot Bypass**: Gestione avanzata di fingerprinting (Canvas, WebGL, AudioContext).

---

## 📊 Algoritmi di Money Management

Il sistema automatizza la gestione del rischio applicando il **Criterio di Kelly** e tabelle di progressione dinamiche.

Tutti i calcoli sono eseguiti nel `BetWorker` in un thread isolato, garantendo che la UI rimanga fluida anche durante operazioni massive.

---

## 🛠️ Setup Tecnico

### Prerequisiti

- **Python 3.10.11** (Versione raccomandata per stabilità PySide6)
- **Chrome** (Avviato con porta di debug: `chrome.exe --remote-debugging-port=9222`)
- **Hardware Vault**: Il sistema richiede l'inizializzazione del `vault.bin` locale per il salvataggio criptato (AES-256) delle chiavi API.

### Installazione (Developer Mode)

```bash
# Clona il repository
git clone https://github.com/petiro/Dom2.git

# Installa le dipendenze (congelate a NumPy 1.26.4 per compatibilità)
pip install -r requirements.txt

# Inizializza Playwright
python -m playwright install chromium
```

### Compilazione Enterprise EXE

Il progetto include una spec di compilazione avanzata che gestisce i browser hooks e riduce i falsi positivi degli antivirus:

```bash
python -m PyInstaller SuperAgent_V4_Enterprise.spec --clean
```

---

## 📦 Struttura del Progetto

- **`core/`**: Logica di business, orchestratori (Sentinel, Guardian) e gestione browser.
- **`ui/`**: Interfaccia grafica basata su PySide6 (Qt).
- **`data/`**: Database locale delle sessioni e file di configurazione (YAML).
- **`main.py`**: Entry point con splash screen asincrono e inizializzazione logger.

---

## 🔍 Repository Audit (Bug & Improvement)

Per scansionare il repository alla ricerca di pattern noti (es. `shell=True`, `except:` bare, TODO/FIXME), esegui:

```bash
python repo_audit.py
```

Il report elenca le occorrenze con percorso e numero di riga.

---

## 📜 Logica di Stabilità V4.x

- **Thread Safety**: Comunicazione sicura via segnali Qt tra Watchdog (thread demone) e Controller (thread principale).
- **Zero-Deadlock**: Gestione del flag `is_pending` centralizzata per prevenire blocchi logici sui segnali Telegram.
- **Auto-Recovery**: Riavvio controllato delle sessioni CDP senza perdita dello stato della scommessa.

---

> **Disclaimer**: Questo software è inteso per scopi di ricerca sull'automazione e l'intelligenza artificiale. L'utente si assume la piena responsabilità per l'uso dello strumento in contesti di gambling reale.
