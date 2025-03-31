from loguru import logger
from curl_cffi.requests import AsyncSession
import random
import asyncio

from src.model.gigaverse.gameClient import GameClient
from src.utils.client import create_client
from src.utils.config import Config
from src.utils.constants import Account

class Start:
    def __init__(
        self,
        account: Account,
        config: Config,
    ):
        self.account = account
        self.config = config

        self.session: AsyncSession | None = None

    async def initialize(self):
        try:
            self.session = await create_client(self.account.proxy)

            return True
        except Exception as e:
            logger.error(f"[{self.account.index}] | Error: {e}")
            return False

    async def flow(self):
        try:

            if self.config.TASK == "AI Giga":
                chatter = GameClient(self.account, self.session, self.config)
                await chatter.run()

            await self.sleep(self.config.TASK)

            return True
        except Exception as e:
            logger.error(f"[{self.account.index}] | Error: {e}")
            return False

    async def sleep(self, task_name: str):
        pause = random.randint(
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
        )
        logger.info(
            f"[{self.account.index}] Sleeping {pause} seconds after {task_name}"
        )
        await asyncio.sleep(pause)
