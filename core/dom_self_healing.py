import logging
# NESSUN altro import custom qui per evitare Circular Import

class DOMSelfHealing:
    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("SelfHealing")
        self._heal_count = 0

    def heal(self, key):
        # 1. Check sicurezza
        if not self.executor: return None

        page = getattr(self.executor, "page", None)
        if not page: return None

        # 2. Anti-Loop
        if self._heal_count > 2:
            self.logger.error("Healing limit reached. Abort.")
            return None

        self._heal_count += 1
        self.logger.warning(f"♻️ SELF-HEAL START: {key}")

        current_url = None
        try: current_url = page.url
        except: pass

        try:
            # 3. IMPORT LOCALE (Deferred)
            # Questo rompe il cerchio dell'importazione
            from core.auto_mapper_worker import AutoMapperWorker
            
            target_url = current_url if current_url else page.url
            mapper = AutoMapperWorker(self.executor, target_url)

            # 4. Lock Thread Safe
            lock = getattr(self.executor, "_internal_lock", None)
            if lock: lock.acquire()

            try:
                # CDP Session
                cdp = page.context.new_cdp_session(page)
                cdp.send("DOM.enable")
                resp = cdp.send("DOM.getFlattenedDocument", {"depth": -1, "pierce": True})
                
                try: cdp.detach()
                except: pass

                nodes = resp.get("nodes", [])
                
                # Metodi interni del mapper
                elements = mapper._extract(nodes)
                selectors = mapper._ai_match(elements)

                if selectors: mapper._save(selectors)

            finally:
                if lock: lock.release()

            # 5. Ripristino Navigazione
            try:
                if current_url and page.url != current_url:
                    page.goto(current_url, timeout=15000)
                    page.wait_for_load_state("domcontentloaded")
            except Exception as nav_err:
                self.logger.warning(f"Return navigation fail: {nav_err}")

            # 6. Risultato
            new_sel = selectors.get(key) if selectors else None
            if new_sel:
                self.logger.info(f"✅ HEALED: {key} -> {new_sel}")
                self._heal_count = 0
                return new_sel

        except Exception as e:
            self.logger.error(f"Self-heal error: {e}")

        return None