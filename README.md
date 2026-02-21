# 🤖 SuperAgent - Trading Automation OS (V8.5 Hedge-Grade)

SuperAgent non è un semplice script o un "bot Python", ma un Sistema Operativo di Automazione Finanziaria (Trading OS) progettato per operare in autonomia totale 24/7 su VPS/Server Dedicati.

È strutturato per intercettare segnali da Telegram, analizzarli tramite AI, mappare i selettori DOM e piazzare scommesse sportive in modo totalmente invisibile ai sistemi anti-frode (Datadome, Akamai), garantendo un uptime del 100% grazie al suo strato di supervisione OS e prevenendo qualsiasi perdita di dati.

---

## 📖 Benvenuto in SUPERAGENT OS! (Guida Rapida)

Se è la prima volta che apri questo programma, non preoccuparti: anche se dietro le quinte c'è una tecnologia di livello finanziario (Hedge-Grade), l'interfaccia è stata studiata per essere semplice e intuitiva. 

Immagina questo programma come il tuo **ufficio virtuale**: qui assumi i tuoi "robot", gli dai le chiavi per accedere ai siti di scommesse, gli spieghi cosa fare e loro lavorano per te 24 ore su 24.

Ecco una guida passo-passo per navigare tra le 6 sezioni (Tab) che trovi in alto:

### 📊 1. Tab: Dashboard (Il Pannello di Controllo)
* **A cosa serve:** È la tua schermata di benvenuto.
* **Come si usa:** Non devi cliccare nulla qui. Ti serve solo per avere un colpo d'occhio. Se vedi la scritta **"SYSTEM STATUS: 🟢 WATCHDOG OS ACTIVE"**, significa che il motore del programma è acceso, i tuoi dati sono al sicuro nel "Vault" (una cassaforte digitale invisibile) e il sistema di backup è attivo.

### 💰 2. Tab: Bookmakers (La tua Cassaforte)
* **A cosa serve:** Qui è dove inserisci le tue credenziali (nome utente e password) dei vari siti di scommesse (es. Bet365, Sisal, ecc.).
* **È sicuro?** Assolutamente sì. Le password che inserisci non vengono mai salvate "in chiaro", ma vengono criptate a livello militare.
* **Come aggiungere un account:**
  1. Vai nel pannello di destra.
  2. Scrivi un **Nome** per ricordarti l'account (es. *Bet365_Mio*).
  3. Inserisci il tuo **Username** e la **Password**.
  4. Clicca sul pulsante **`➕ Salva Bookmaker`**. Vedrai l'account comparire nella lista a sinistra.
* **Come eliminare un account:** Clicca sul nome dell'account nella lista a sinistra e premi **`❌ Elimina Selezionato`**.

### 🧩 3. Tab: Selettori (Gli "Occhi" del Bot)
* **A cosa serve:** I siti web cambiano spesso. Qui è dove "insegni" al bot dove si trovano esattamente i pulsanti sui vari siti web (es. dove cliccare per scommettere).
* **Come si usa:**
  1. Scegli un **Nome** per l'istruzione (es. *pulsante_scommetti*).
  2. Seleziona a quale **Bookmaker** si riferisce.
  3. Incolla il codice "CSS" o "XPath" (è il "percorso" tecnico del pulsante sul sito web).
  4. Clicca su **`➕ Salva Selettore`**.

### 🤖 4. Tab: Robot & Strategie (Il Cervello)
* **A cosa serve:** Qui crei le tue strategie. Puoi creare quanti robot vuoi, assegnare a ciascuno un budget e dirgli a quali parole (inviate su Telegram) deve reagire.
* **Come creare una strategia:**
  1. Clicca sul pulsante in basso **`➕ Crea Nuovo Robot`**.
  2. Guardando il pannello di destra, dagli un **Nome**.
  3. Scegli dal menu a tendina quale **Account Bookmaker** (che hai salvato nella Tab 2) questo robot dovrà usare.
  4. Inserisci le **Trigger Words** (parole chiave separate da virgola, es: *calcio, over 2.5, serie a*). Quando il bot leggerà queste parole su Telegram, si attiverà.
  5. Imposta lo **Stake** (l'importo fisso in Euro da scommettere).
* 💡 **NOTA MAGICA:** Hai notato che non c'è il pulsante "Salva"? In questa schermata **il salvataggio è automatico e istantaneo**. Ogni lettera che digiti viene salvata in tempo reale. Se va via la corrente, non perdi nulla!
* **Come eliminare un robot:** Selezionalo a sinistra e clicca **`❌ Elimina Robot`**.

### ☁️ 5. Tab: Cloud & API (I Collegamenti Esterni)
* **A cosa serve:** Il tuo bot ha bisogno di "parlare" con Telegram (per leggere i pronostici) e con l'Intelligenza Artificiale (per capirli). Qui inserisci i codici segreti (API) per permettere questa comunicazione.
* **Come si usa:**
  1. Incolla i tuoi codici di Telegram (`API ID`, `API Hash` e la lunghissima `Session String`).
  2. Incolla la tua `API Key` di OpenRouter (il cervello dell'IA).
  3. Clicca su **`💾 Salva Chiavi API & Cloud`**.
* **Nota di Sicurezza:** Appena salvi, i codici si trasformeranno in pallini o asterischi per proteggere la tua privacy da chiunque guardi il tuo schermo.

### 📝 6. Tab: Logs (La Scatola Nera)
* **A cosa serve:** È il monitor in stile "hacker" (sfondo nero, scritte verdi). Ti mostra in diretta tutto quello che il bot sta facendo in quel preciso istante.
* **Come si usa:** Non devi fare assolutamente nulla. Siediti e guarda le scritte scorrere. Vedrai il bot che riceve i segnali, ragiona, si connette ai bookmaker e piazza le scommesse.

### 🚦 IN CHE ORDINE DEVO PROCEDERE LA PRIMA VOLTA?
Per non confonderti, segui questo ordine esatto per la prima configurazione:
1. Vai su **Cloud & API** e collega Telegram e l'Intelligenza artificiale.
2. Vai su **Bookmakers** e inserisci il tuo conto di gioco (es. Bet365).
3. Vai su **Selettori** (se hai codici da aggiornare per i siti).
4. Vai su **Robot & Strategie** e crea il tuo primo lavoratore virtuale, dicendogli quanti soldi usare e quale account scommesse gestire.
5. Vai su **Logs**, rilassati e lascia che il bot faccia il lavoro sporco!

---

## 📂 Struttura del Repository

Ecco l'elenco completo di tutti i file attualmente caricati e disponibili nell'ambiente:

**Directory Principale / Root (`/`):**
* `.gitignore`, `AUDIT_REPORT.md`, `README.md`, `hedge_super_tester.py`, `main.py`, `pyproject.toml`, `quant_ci_evaluator.py`, `repo_audit.py`, `requirements.txt`, `setup_vps_task.py`, `supervisor.py`, `tester_v4.py`

**Directory `.github/workflows/`:**
* `build.yml`, `openrouter_audit.yml`, `production_check.yml`, `v4_test_suite.yml`, `v7_quant_monitoring.yml`

**Directory `config/`:**
* `config.yaml`, `robots.yaml`, `selectors.yaml`

**Directory `core/`:**
* `ai_parser.py`, `ai_selector_validator.py`, `ai_trainer.py`, `anti_detect.py`, `arch_v6.py`, `auto_mapper_worker.py`, `bet_worker.py`, `command_parser.py`, `config_loader.py`, `config_paths.py`, `controller.py`, `crypto_vault.py`, `database.py`, `dom_executor_playwright.py`, `dom_self_healing.py`, `event_bus.py`, `events.py`, `execution_engine.py`, `geometry.py`, `health.py`, `heartbeat.py`, `human_behavior.py`, `human_mouse.py`, `lifecycle.py`, `logger.py`, `money_management.py`, `multi_site_scanner.py`, `os_human_interaction.py`, `playwright_worker.py`, `secure_storage.py`, `security.py`, `security_logger.py`, `signal_parser.py`, `state_machine.py`, `telegram_worker.py`, `utils.py`

**Directory `ui/`:**
* `bookmaker_tab.py`, `desktop_app.py`, `robots_tab.py`, `selectors_tab.py`

---

## 🧪 Ingegneria del Caos e Suite di Test (`tests/`)

SuperAgent non è testato con semplici "Unit Test", ma con una vera e propria suite di **Ingegneria del Caos (Chaos Engineering)** progettata per simulare i peggiori disastri possibili in ambiente di produzione VPS. 

La directory `tests/` è divisa in due categorie principali: `system_integrity` e `stress_lab`.

### 🛡️ System Integrity (Test Architetturali)
Questi script collaudano le fondamenta finanziarie e la resilienza del Core:

* **`ULTRA_SYSTEM_TEST.py` (Architectural Chaos Simulation):**
  Il collaudo definitivo. Simula disastri architetturali per garantire la protezione del capitale:
  * *Double Bet:* Uccide il bot un istante prima della conferma scommessa e verifica che al riavvio i fondi non siano "zombie" (Two-Phase Commit).
  * *Event Bus Block:* Verifica che messaggi Telegram lenti non blocchino il motore di scommessa (Asincronia totale).
  * *Financial Watchdog:* Controlla che il bot si accorga se il bookmaker annulla una scommessa esternamente.
  * *Over-reserve & Math Poison:* Simula 50 attacchi simultanei al database tentando di prelevare più soldi del bankroll e inietta input matematici corrotti (NaN/Infinito) per validare i lock di SQLite (PRAGMA WAL).

* **`ENDURANCE_TEST.py` (Extreme Survival Simulation):**
  Simula il degrado ambientale della VPS nel tempo:
  * *Disk Full:* Finge che il disco della VPS sia pieno a metà di una scrittura SQLite.
  * *Cloudflare Ban:* Inietta finti timeout di 30 secondi per testare la fuga dal browser.
  * *Memory Leak (Soak Test):* Spara 4.000 segnali spazzatura consecutivi in pochi secondi monitorando l'allocazione della RAM per assicurarsi che il bot non vada mai in Out-Of-Memory.

### 🌪️ Stress Lab (Monitoraggio & Intelligenza)
Questa sezione ospita i test quantitativi e le simulazioni dell'Execution Engine:

* **`GOD_MODE_chaos.py`:** Il distruttore supremo. Genera eccezioni casuali, fa cadere finte connessioni internet e cambia il DOM del browser mentre il bot sta cliccando, verificando che le routine di Self-Healing ripristinino sempre lo stato.
* **`super_tester_v7.py`:** Esegue decine di simulazioni End-to-End. Passa finti messaggi Telegram all'AI, riceve il JSON formattato e avvia l'intero ciclo vitale fino alla scommessa.
* **`quant_monitor.py` & `stability_metrics.py`:** Moduli di telemetria. Tracciano il Win Rate dell'AI (percentuale di parsing corretto), i tempi di esecuzione in millisecondi e l'uptime generale del sistema generando un report statistico.
* **`mock_executor.py`:** Un "finto" browser Playwright. Permette alla suite di test di simulare migliaia di navigazioni, estrazioni quote e click senza dover aprire una vera finestra di Chrome, abbattendo il tempo di test da ore a secondi.

---

## 🌟 Il Ciclo di Vita del Sistema (24/7 Unattended)

Il sistema è progettato per non fermarsi letteralmente mai. Ecco come si comporta in produzione:

* **Il Risveglio (Supervisor):** L'esecuzione non parte da `main.py`, ma da `supervisor.py` (installato come Task di Sistema in Windows). Questo guardiano esterno lancia il Core e resta in ascolto.
* **Il Battito Cardiaco (Heartbeat):** Il Core emette un "pulsare" ogni 10 secondi (`heartbeat.dat`). Se Chromium va in deadlock, la rete salta o il GIL di Python si congela, l'impulso si ferma. Dopo 60 secondi di silenzio, il Supervisor esegue un Hard Kill dell'albero dei processi e resuscita il sistema istantaneamente.
* **Il Vault (Persistenza Sicura):** All'avvio, il sistema non usa file di configurazione nel repository. Accede alla cartella segreta `~/.superagent_data/`, decripta le credenziali in memoria tramite AES-256 e carica la sessione immortale di Telegram.
* **L'Ascolto (Event Bus):** Il nodo Telegram legge i segnali dai tipster in modo asincrono e li spara nell'Event Bus.
* **L'Intelligenza (AI & Rules):** L'AI interpreta il segnale, capisce se rispetta le regole dei Robot impostati (stake, esclusione parole, mercato) ed estrapola l'azione.
* **L'Azione (RPA Stealth V4):** Playwright si avvia iniettando il codice Anti-Detect prima del caricamento pagina. Usa curve di Bézier per simulare il movimento del mouse umano, logga, piazza la scommessa, verifica il saldo reale e chiude.
* **Il Sonno Sicuro (Auto-Backup):** Ogni 30 minuti, un demone silenzioso applica un Lock Atomico al database SQLite, clona l'intero Vault crittografato e crea uno `.zip` (Disaster Recovery).

---

## 🚀 Architettura e Moduli Principali

### 🔐 1. OpSec & Sicurezza Militare (Crypto Vault)
* **Zero Leak Repository:** Nessuna API Key, password o StringSession viene mai salvata nel codice o in config.yaml.
* **Storage Isolato:** I dati risiedono fuori dal repo, nella root utente (`~/.superagent_data/`).
* **Crittografia AES-256:** Le password dei bookmaker inserite nella UI vengono crittografate su disco con una `.master.key` unica per macchina.
* **SecretFilter Globale:** Il sistema di logging analizza ogni stringa in nanosecondi, mascherando eventuali token API con `██SECRET_MASKED██`.

### 🛟 2. Resilienza e Disaster Recovery
* **Atomic SQLite Backup:** Usa l'API nativa `sqlite3.backup()` per clonare il database dei fondi a livello C++.
* **Hard Recycle Preventivo:** Se Chromium inizia a soffrire di memory leak superando i 1.2GB di RAM, il processo viene piallato e ricaricato pulito tra una bet e l'altra.
* **Auto-Boot Windows Task:** Script di installazione (`setup_vps_task.py`) che infila il bot nello SchTasks di Windows con privilegi di amministratore.

### 🕵️‍♂️ 3. Ingegneria Anti-Detect
* **Iniezione JS V4:** Modifica di `navigator.webdriver`, falsificazione dei plugin di sistema, WebGL vendor masking e noise injection su Canvas.
* **Human Mouse:** Il mouse viaggia sullo schermo rallentando in prossimità del target con lievi tremolii (Jitter).
* **Doppia Conferma Finanziaria:** Nessuna scommessa viene considerata "Piazzata" se il saldo del bookmaker non risulta effettivamente decurtato (Circuit Breaker Finanziario).

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
