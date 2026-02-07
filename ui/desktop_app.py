def process_new_signal(self, data):
    self.logger.info(f'Received new signal with data: {data}')
    try:
        self.rpa_worker.enqueue_bet(data)
    except Exception as e:
        self.logger.error(f'Error processing new signal: {e}')
