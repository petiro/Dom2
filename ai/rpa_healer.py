"""
RPA Self-Healing System - Production Grade
Sistema a due livelli: Analisi DOM (veloce) + Vision AI (fallback).
Gestisce la riparazione automatica dei selettori corrotti o cambiati.
"""
import json
import os
import yaml
import shutil
import base64
from typing import Dict, List, Optional
from datetime import datetime
from ai.vision_learner import VisionLearner
from dom_scanner import scan_dom

class RPAHealer:
    def __init__(self, vision_learner: VisionLearner, logger=None,
                 selectors_file: str = "config/selectors.yaml",
                 backup_dir: str = "data/selector_backups",
                 confidence_threshold: float = 0.8):
        
        self.vision = vision_learner
        self.logger = logger
        self.selectors_file = selectors_file
        self.backup_dir = backup_dir
        self.confidence_threshold = confidence_threshold
        
        self.healing_history = []
        self.history_file = "data/healing_history.json"
        
        # Assicura l'esistenza delle cartelle
        os.makedirs(backup_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        self._load_history()

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.healing_history = json.load(f)
            except Exception:
                self.healing_history = []

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.healing_history[-100:], f, indent=2) # Mantieni ultimi 100
        except Exception:
            pass

    def _backup_selectors(self):
        """Crea una copia di sicurezza di selectors.yaml prima di modificarlo."""
        if os.path.exists(self.selectors_file):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"selectors_backup_{timestamp}.yaml")
            shutil.copy2(self.selectors_file, backup_path)
            
            # Mantieni solo gli ultimi 5 backup
            backups = sorted([os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir)])
            if len(backups) > 5:
                for old_backup in backups[:-5]:
                    os.remove(old_backup)

    def heal_and_fix(self, page, failed_selector_key, selectors_dict):
        """
        Tenta di riparare un selettore rotto.
        1. Tier 1: Analisi DOM (Veloce)
        2. Tier 2: Vision AI su Screenshot (Lento/Costoso)
        """
        if self.logger:
            self.logger.warning(f"💊 Avvio auto-healing per il selettore: {failed_selector_key}")

        new_selector = None
        
        try:
            # --- TIER 1: Analisi del DOM ---
            dom_data = scan_dom(page)
            # Chiediamo all'AI di identificare l'elemento nei dati testuali del DOM
            new_selector = self.vision.find_element_in_dom(dom_data, failed_selector_key)

            # --- TIER 2: Fallback su Visione Reale (Screenshot) ---
            if not new_selector:
                if self.logger:
                    self.logger.info("Tier 1 fallito. Provo con analisi visiva (Screenshot)...")
                
                screenshot_path = f"logs/healing_vision_{failed_selector_key}.png"
                page.screenshot(path=screenshot_path)
                
                # L'AI guarda l'immagine e restituisce il selettore CSS
                new_selector = self.vision.analyze_screenshot_for_selector(screenshot_path, failed_selector_key)

            if new_selector:
                self._apply_fix(failed_selector_key, new_selector, selectors_dict)
                return new_selector

        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Errore durante il processo di healing: {e}")
        
        return None

    def _apply_fix(self, key, new_val, selectors_dict):
        """Applica la correzione, salva su file e registra l'evento."""
        self._backup_selectors()
        
        selectors_dict[key] = new_val
        
        try:
            with open(self.selectors_file, 'w', encoding='utf-8') as f:
                yaml.dump(selectors_dict, f, default_flow_style=False)
            
            if self.logger:
                self.logger.info(f"✅ Selettore '{key}' aggiornato con successo: {new_val}")
            
            # Registra nella storia
            self.healing_history.append({
                "timestamp": datetime.now().isoformat(),
                "selector_key": key,
                "new_selector": new_val,
                "status": "repaired"
            })
            self._save_history()
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Errore durante il salvataggio di selectors.yaml: {e}")

    def get_stats(self):
        """Restituisce statistiche sull'auto-riparazione."""
        return {
            "total_repairs": len(self.healing_history),
            "last_repair": self.healing_history[-1] if self.healing_history else None
        }
