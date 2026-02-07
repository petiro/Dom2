import asyncio
import logging
import os
import signal
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai import AIFactory

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
def load_config(filepath):
    with open(filepath) as f:
        return json.load(f)

# Singleton Class
class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance

class ExecutorSingleton(Singleton):
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count())

# AI initialization
class AI:
    def __init__(self):
        self.factory = AIFactory()

    async def run(self):
        # AI run logic
        pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.on_event("startup")
async def startup_event():
    config = load_config('config.json')
    logger.info('Loaded config: %s', config)

    # Initializing AI
    ai_instance = AI()
    await ai_instance.run()

    # Create executor
    executor = ExecutorSingleton()  # Singleton instance

@app.on_event("shutdown")
def shutdown_event():
    # Kill Chrome and clean up
    os.system('pkill chrome')

async def run_app(executor):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, some_function)

if __name__ == '__main__':
    executor = ExecutorSingleton().executor
    try:
        asyncio.run(run_app(executor))
    except KeyboardInterrupt:
        logger.info('App stopped manually')