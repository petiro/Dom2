# AUDIT COMPLETO REPOSITORY — SuperAgent V5.9

**Data:** 2026-02-14
**File analizzati:** 38
**Linee di codice Python:** ~3.700

---

## LEGENDA SEVERITA

| Livello | Significato |
|---------|------------|
| **CRITICO** | Bug che causa crash o comportamento errato garantito |
| **ALTO** | Bug che causa malfunzionamenti in scenari reali |
| **MEDIO** | Problema di qualita/manutenibilita che puo causare bug futuri |
| **BASSO** | Miglioramento consigliato |

---

## BUG CRITICI

### BUG-01: `signal_parser.py` ritorna chiave `"match"`, il controller si aspetta `"teams"`
**Severita:** CRITICO
**File:** `core/signal_parser.py:22` → `core/controller.py:120`
**Descrizione:** `TelegramSignalParser.parse()` ritorna `{"match": ..., "market": ...}` ma il controller controlla `data.get("teams")`. Il parser legacy non produrra MAI un risultato valido — il fallback e inutile.

---

### BUG-02: `mapping_tab.py` referenzia attributi inesistenti sul controller
**Severita:** CRITICO
**File:** `ui/mapping_tab.py:17,95-96,119`
**Descrizione:** Tre riferimenti a metodi/attributi che non esistono su `SuperAgentController`:
- `controller.mapping_ready` (Signal mai definito) — crash alla connessione del segnale (linea 17)
- `controller.vault` (attributo mai assegnato) — crash su `save_api_key()` (linea 95)
- `controller.save_selectors_yaml()` (metodo inesistente) — crash su `save_yaml()` (linea 119)

---

### BUG-03: `bet_worker.py` chiama metodi inesistenti
**Severita:** CRITICO
**File:** `core/bet_worker.py:19,26`
**Descrizione:**
- `self.executor.find_odds()` — `DomExecutorPlaywright` non ha questo metodo
- `self.money_manager.calculate_stake()` — `MoneyManager` ha `get_stake()`, non `calculate_stake()`

---

### BUG-04: `telegram_tab.py` chiama `controller.connect_telegram()` inesistente
**Severita:** CRITICO
**File:** `ui/telegram_tab.py:110`
**Descrizione:** Il metodo `connect_telegram()` non esiste su `SuperAgentController`. Premere "Salva e Connetti" causa un `AttributeError`.

---

### BUG-05: `main_v6.py` — QObject creato prima di QApplication
**Severita:** CRITICO
**File:** `main_v6.py:19`
**Descrizione:** `logger, _ = setup_logger()` eseguito a livello di modulo crea un `LogSignaler(QObject)` prima che esista una `QApplication`. Questo puo causare crash o warning su diverse piattaforme Qt.

---

### BUG-06: Doppia definizione di `SystemWatchdog`
**Severita:** ALTO
**File:** `core/health.py:13` e `core/lifecycle.py:24`
**Descrizione:** `SystemWatchdog` e definito sia in `health.py` (come `QObject`) che in `lifecycle.py` (come `QThread`). `main.py` importa da `health.py`, rendendo la versione completa in `lifecycle.py` (con monitoraggio RAM, browser, etc.) completamente inutilizzata.

---

### BUG-07: Directory duplicata `core/core/` con implementazioni diverse
**Severita:** ALTO
**File:** `core/core/config_loader.py` vs `core/config_loader.py`
**Descrizione:** Esistono due file `config_loader.py`:
- `core/config_loader.py` — carica secrets.json e merge con YAML (versione usata)
- `core/core/config_loader.py` — maschera i dati sensibili (versione orfana)

Stessa situazione per `ai_selector_validator.py`. La directory `core/core/` e probabilmente residuo di un refactoring incompleto.

---

### BUG-08: Percorsi relativi inconsistenti (dipendenza da CWD)
**Severita:** ALTO
**File:** Multipli
**Descrizione:** Alcuni moduli usano `get_project_root()` per percorsi assoluti, altri usano percorsi relativi. Se l'app viene avviata da una directory diversa dalla root del progetto, questi file non verranno trovati:
- `desktop_app.py:235` — `"config/money_config.json"` (relativo)
- `desktop_app.py:566` — `"config/secrets.json"` (relativo)
- `dom_executor_playwright.py:130` — `f"config/{self.selector_file}"` (relativo)
- `config_loader.py:29` — `path="config/config.yaml"` (parametro default relativo)

Mentre `money_management.py` e `controller.py` usano correttamente `get_project_root()`.

---

## BUG MEDI

### BUG-09: `CommandParser` creato ma mai usato nel flusso operativo
**Severita:** MEDIO
**File:** `core/controller.py:58,110-129`
**Descrizione:** Il `CommandParser` viene istanziato e collegato al controller, ma `handle_telegram_signal()` salta completamente il sistema di `TaskStep` e chiama direttamente `_execute_bet_logic()`. Tutta la logica di retry/healing del `CommandParser` e ignorata.

---

### BUG-10: `HumanInput` (human_behavior.py) mai utilizzato
**Severita:** MEDIO
**File:** `core/human_behavior.py` (intero file)
**Descrizione:** La classe `HumanInput` con Bezier curves sofisticate non e mai importata. `DomExecutorPlaywright` implementa un proprio `_human_move_and_click()` piu semplice (linee 87-116). Il codice avanzato e completamente morto.

---

### BUG-11: `StateManager` definito ma mai utilizzato
**Severita:** MEDIO
**File:** `core/state_machine.py` (intero file)
**Descrizione:** Lo `StateManager` con transizioni validate, callbacks e history non e mai istanziato dal controller ne da nessun altro modulo. Il controller non ha gestione degli stati.

---

### BUG-12: `core_loop.py` e `core_services.py` mai importati
**Severita:** MEDIO
**File:** `core_loop.py`, `core_services.py`
**Descrizione:** Nessun file nel progetto importa `CoreLoop` o `CoreServices`. Sono codice morto.

---

### BUG-13: `ai_trainer.py` chiama metodi inesistenti sull'executor
**Severita:** MEDIO
**File:** `core/ai_trainer.py:190,198`
**Descrizione:** `train_step()` e `heal_selector()` chiamano:
- `self._executor.get_dom_snapshot()` — non esiste su `DomExecutorPlaywright`
- `self._executor.take_screenshot_b64()` — non esiste su `DomExecutorPlaywright`

Queste funzionalita non possono funzionare fino a quando i metodi non vengono implementati.

---

### BUG-14: Odds hardcoded a `2.0` nel controller
**Severita:** MEDIO
**File:** `core/controller.py:144`
**Descrizione:** `odds = 2.0` e hardcoded. Il commento dice `TODO: Implementare self.executor.get_live_odds()`. Il calcolo dello stake Roserpina dipende da odds reali — con odds fissi il money management non funziona correttamente.

---

### BUG-15: `except: pass` pervasivo — errori finanziari silenti
**Severita:** MEDIO
**File:** `core/controller.py:182,190,196`, `core/money_management.py:27,42,95`, `ui/desktop_app.py:249,265,357,362,408`
**Descrizione:** `except: pass` (bare except) usato in 15+ punti, incluse operazioni finanziarie critiche:
- `_save_to_history` (controller.py:190) — record scommesse persi silenziosamente
- `save_state` (money_management.py:42) — stato Roserpina non salvato
- `_load_history` (controller.py:182) — cattura anche `SystemExit` e `KeyboardInterrupt`

---

## MIGLIORAMENTI

### IMP-01: `pyautogui` mancante da `requirements.txt`
**File:** `requirements.txt`, `core/os_human_interaction.py`
**Descrizione:** `os_human_interaction.py` importa `pyautogui` con fallback, ma non e listato nelle dipendenze.

---

### IMP-02: `get_project_root()` duplicato 4 volte
**File:** `core/config_loader.py:6`, `core/money_management.py:4`, `ui/desktop_app.py:23`, `core/utils.py:8`
**Descrizione:** La stessa funzione e copiata in 4 file diversi. Dovrebbe essere centralizzata in `core/utils.py` e importata ovunque.

---

### IMP-03: Nessun `__init__.py` nelle packages
**File:** `core/`, `ui/`
**Descrizione:** Manca `__init__.py` in entrambe le directory. Funziona come namespace package in Python 3, ma e pratica migliore avere file espliciti per chiarezza e per evitare problemi con PyInstaller.

---

### IMP-04: Versione inconsistente ovunque
**File:** `config/config.yaml:8`, `main_v6.py:25`, `ui/desktop_app.py:593`, `config/config.yaml:3`
**Descrizione:** Riferimenti a versioni diverse:
- config.yaml header: "V8 SENTINEL EDITION"
- config.yaml version field: "5.5"
- main_v6.py: "V5.6"
- desktop_app.py title: "V5.9"

---

### IMP-05: Secrets in chiaro su file JSON
**File:** `config/secrets.json`
**Descrizione:** Le API key sono salvate in plaintext JSON. La classe `Vault` (security.py) esiste ed offre encryption Fernet, ma non e usata dal sistema di settings/config. Il flusso salvataggio dalla UI scrive direttamente JSON non cifrato.

---

### IMP-06: `tester_v4.py` — Test suite quasi vuota
**File:** `tester_v4.py`
**Descrizione:** I "test" verificano solo che le classi si istanzino senza errore. Non ci sono test funzionali, di integrazione, ne unit test reali. Manca un framework di test (pytest).

---

### IMP-07: `desktop_app.py` ha la propria `MappingTab` — file `ui/mapping_tab.py` e codice morto
**File:** `ui/desktop_app.py:453`, `ui/mapping_tab.py`
**Descrizione:** `desktop_app.py` definisce una `MappingTab` interna semplice. `ui/mapping_tab.py` ha una versione piu completa con progress bar e API key management, ma non e mai importata.

---

### IMP-08: Nessun meccanismo di retry per chiamate API
**File:** `core/ai_parser.py:31-48`
**Descrizione:** Le chiamate HTTP a OpenRouter non hanno retry. `auto_mapper_worker.py` ha un sistema di fallback tra modelli ma non retry sullo stesso modello. Una singola timeout di rete causa fallimento completo.

---

### IMP-09: Thread safety sulla history del controller
**File:** `core/controller.py:178-192`
**Descrizione:** `_load_history()` non usa il lock, ma `_save_to_history()` si. Se la history viene letta (es. dalla UI StatsTab.refresh()) mentre un thread la scrive, possibile race condition.

---

### IMP-10: `DomExecutorPlaywright` non chiude risorse nel caso di fallimento parziale
**File:** `core/dom_executor_playwright.py:41-65`
**Descrizione:** Se `connect_over_cdp` riesce ma `contexts[0]` fallisce, `self.pw` resta aperto ma `self.browser` e `None`. La successiva chiamata a `close()` salterebbe la pulizia del browser.

---

## RIEPILOGO

| Categoria | Conteggio |
|-----------|-----------|
| Bug Critici | 8 |
| Bug Medi | 7 |
| Miglioramenti | 10 |
| **Totale Issues** | **25** |

### Top 5 Priorita

1. **BUG-01** — Fix chiave `"match"` → `"teams"` nel signal_parser (il fallback parser e rotto)
2. **BUG-02/03/04** — Implementare metodi mancanti sul controller o aggiornare i chiamanti
3. **BUG-08** — Standardizzare tutti i percorsi file con `get_project_root()`
4. **BUG-06/07** — Rimuovere duplicati (`core/core/`, doppio `SystemWatchdog`)
5. **BUG-15** — Sostituire `except: pass` con `except Exception as e: logger.error(...)` almeno per le operazioni finanziarie
