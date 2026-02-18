import time
import logging
from core.auto_mapper_worker import AutoMapperWorker

class MultiSiteScanner:
    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("Scanner")

    def scan(self, urls):
        results = {}
        for url in urls:
            try:
                self.logger.info(f"Scan sito: {url}")
                mapper = AutoMapperWorker(self.executor, url)
                mapper.run()
                results[url] = "Done"
                time.sleep(3)
            except Exception as e:
                self.logger.error(f"Scan error {url}: {e}")
                results[url] = str(e)
        return results
