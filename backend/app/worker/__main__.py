"""Run one sequential polling worker; multiple processes coordinate through PostgreSQL."""

import asyncio
import logging
import signal

from backend.app.core.config import get_settings
from backend.app.database.session import AsyncSessionLocal, engine
from backend.app.worker.checkpoints import open_checkpointer
from backend.app.worker.runner import Worker
from civicmesh_ai.providers.gemini import GeminiProvider


async def main():
    settings = get_settings()
    provider = GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(name, stop.set)
        except NotImplementedError:  # Windows development shell.
            pass
    async with open_checkpointer(settings) as saver:
        worker = Worker(
            sessions=AsyncSessionLocal,
            engine=engine,
            provider=provider,
            saver=saver,
            settings=settings,
        )
        await worker.heartbeat()

        async def pulse():
            while not stop.is_set():
                await worker.heartbeat()
                await asyncio.sleep(10)

        task = asyncio.create_task(pulse())
        try:
            while not stop.is_set():
                # A failed heartbeat stops intake: an unreachable database is not healthy.
                if task.done():
                    await task
                if not await worker.run_once():
                    try:
                        await asyncio.wait_for(stop.wait(), settings.WORKER_POLL_INTERVAL_SECONDS)
                    except TimeoutError:
                        pass
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await provider.client.aio.aclose()
            await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as error:
        logging.getLogger("civicmesh.worker").error("Worker stopped: %s", type(error).__name__)
        raise SystemExit(1) from None
