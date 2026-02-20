 🤖 SuperAgent - Trading Automation OS (V8.5 Hedge-Grade)

SuperAgent non è un semplice script o un "bot Python", ma un **Sistema Operativo di Automazione Finanziaria (Trading OS)** progettato per operare in autonomia totale 24/7 su VPS/Server Dedicati.

È strutturato per intercettare segnali da Telegram, analizzarli tramite AI, mappare i selettori DOM e piazzare scommesse sportive in modo totalmente invisibile ai sistemi anti-frode (Datadome, Akamai), garantendo un uptime del 100% grazie al suo strato di supervisione OS e prevenendo qualsiasi perdita di dati.

---

## 🌟 Il Ciclo di Vita del Sistema (24/7 Unattended)

Il sistema è progettato per non fermarsi letteralmente **mai**. Ecco come si comporta in produzione:

1. **Il Risveglio (Supervisor):** L'esecuzione non parte da `main.py`, ma da `supervisor.py` (installato come Task di Sistema in Windows). Questo guardiano esterno lancia il Core e resta in ascolto.
2. **Il Battito Cardiaco (Heartbeat):** Il Core emette un "pulsare" ogni 10 secondi (`heartbeat.dat`). Se Chromium va in deadlock, la rete salta o il GIL di Python si congela, l'impulso si ferma. Dopo 60 secondi di silenzio, il Supervisor esegue un *Hard Kill* dell'albero dei processi e resuscita il sistema istantaneamente.
3. **Il Vault (Persistenza Sicura):** All'avvio, il sistema non usa file di configurazione nel repository. Accede alla cartella segreta `~/.superagent_data/`, decripta le credenziali in memoria tramite **AES-256** e carica la sessione immortale di Telegram.
4. **L'Ascolto (Event Bus):** Il nodo Telegram legge i segnali dai tipster in modo asincrono e li spara nell'Event Bus.
5. **L'Intelligenza (AI & Rules):** L'AI interpreta il segnale, capisce se rispetta le regole dei *Robot* impostati (stake, esclusione parole, mercato) ed estrapola l'azione.
6. **L'Azione (RPA Stealth V4):** Playwright si avvia iniettando il codice Anti-Detect prima del caricamento pagina. Usa curve di Bézier per simulare il movimento del mouse umano, logga, piazza la scommessa, verifica il saldo reale e chiude.
7. **Il Sonno Sicuro (Auto-Backup):** Ogni 30 minuti, un demone silenzioso applica un Lock Atomico al database SQLite, clona l'intero Vault crittografato e crea uno `.zip` (Disaster Recovery).

---

## 🚀 Architettura e Moduli Principali

### 🔐 1. OpSec & Sicurezza Militare (Crypto Vault)

* **Zero Leak Repository:** Nessuna API Key (OpenRouter), password o StringSession viene mai salvata nel codice o in `config.yaml`.
* **Storage Isolato:** I dati risiedono fuori dal repo, nella root utente (`~/.superagent_data/`). Disinstallare o aggiornare il bot tramite git non causa perdita di bankroll o impostazioni.
* **Crittografia AES-256:** Le password dei bookmaker inserite nella UI vengono crittografate su disco con una `.master.key` unica per macchina.
* **SecretFilter Globale:** Il sistema di logging analizza ogni stringa in nanosecondi. Se individua una chiave API o un Token che per errore sta per finire nei log di testo o a schermo, lo maschera irreversibilmente con `██SECRET_MASKED██`.

### 🛟 2. Resilienza e Disaster Recovery

* **Atomic SQLite Backup:** Usa l'API nativa `sqlite3.backup()` per clonare il database dei fondi a livello C++, prevenendo la corruzione in caso di crash durante la scrittura.
* **Hard Recycle Preventivo:** Se Chromium inizia a soffrire di *memory leak* superando i 1.2GB di RAM, il processo viene piallato e ricaricato pulito tra una bet e l'altra.
* **Auto-Boot Windows Task:** Script di installazione (`setup_vps_task.py`) che infila il bot nello *SchTasks* di Windows con privilegi di amministratore. Se il VPS si riavvia di notte, SuperAgent è già operativo prima del login.

### 🕵️‍♂️ 3. Ingegneria Anti-Detect

* **Iniezione JS V4:** Modifica di `navigator.webdriver`, falsificazione dei plugin di sistema, WebGL vendor masking e noise injection su Canvas.
* **Human Mouse:** Il mouse non si teletrasporta (`click()`), ma viaggia sullo schermo rallentando in prossimità del target con lievi tremolii (Jitter).
* **Doppia Conferma Finanziaria:** Nessuna scommessa viene considerata "Piazzata" se il saldo del bookmaker, letto dal DOM *dopo* l'azione, non risulta effettivamente decurtato (Circuit Breaker Finanziario).

### 🧠 4. Piattaforma Multi-Tenant (GUI)

* **Bookmaker Manager:** Gestione di infiniti account (es. *Bet365_Main*, *Sisal_P1*) associabili a robot diversi.
* **Robot & Strategy Manager:** Creazione di agenti autonomi indipendenti. Ogni robot ha i propri trigger, la sua gestione del capitale (Fisso o Progressioni) e il suo target di bookmaker.
* **Selettori AI:** Possibilità di iniettare XPath/CSS personalizzati senza toccare il codice, salvandoli stabilmente nel Vault. Utile se il bookmaker cambia interfaccia.
* **Telegram Session Immortale:** Zero file `.session` temporanei. Accesso tramite StringSession auto-rigenerante che non richiede mai più di un SMS di accesso nella vita.

---

## 📁 Struttura del Vault di Produzione

In ambiente Live, il sistema dipende dalla cartella locale e protetta:

```text
C:\Users\TUO_NOME\.superagent_data\
 ├── .master.key               # Chiave militare generata al primo avvio
 ├── heartbeat.dat             # Pulsazione vitale letta dal Supervisor
 ├── money_db.sqlite           # Database tracking scommesse e ROI
 ├── telegram_session.dat      # Login immortale
 ├── openrouter_key.dat        # API Key AI (Mai su GitHub)
 ├── bookmakers.json           # Account bookmaker con PWD crittografate
 ├── robots.json               # I bot e le logiche di puntata
 ├── selectors.json            # Mappatura DOM (XPath/CSS)
 └── backups/
      └── superagent_backup_20260220_1530.zip # Archivio zippato auto-generato

```

---

## 💻 Installazione e Deploy (VPS)

### 1. Requisiti e Dipendenze

Installa Python 3.10+ e le dipendenze di crittografia e OS:

```bash
pip install -r requirements.txt
python -m playwright install chromium

```

### 2. Configurazione VPS (Esegui 1 volta sola)

Per rendere il bot immortale ai riavvii di Windows Server, apri il terminale **come Amministratore** ed esegui:

```bash
python setup_vps_task.py

```

### 3. Avvio Quotidiano

In produzione, non interagire mai direttamente con il file del codice. Usa il Supervisor:

```bash
python supervisor.py

```

---

## ⚠️ Sicurezza e Responsabilità

SuperAgent OS gestisce capitali reali ed è progettato con strumenti elusivi avanzati.
Anche se le protezioni interne prevengono il leak di credenziali via log, è responsabilità dell'utente mantenere inviolato il server VPS e il contenuto crittografato della directory `~/.superagent_data/`.
