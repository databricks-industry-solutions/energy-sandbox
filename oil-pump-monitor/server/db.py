import os
import asyncpg
import asyncio
from typing import Optional
from .config import get_oauth_token, IS_DATABRICKS_APP

class DatabasePool:
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._demo_mode = False
        self._refresh_task: Optional[asyncio.Task] = None

    async def get_pool(self) -> Optional[asyncpg.Pool]:
        if not os.environ.get("PGHOST"):
            self._demo_mode = True
            return None

        if self._pool is None:
            try:
                token = get_oauth_token()
                self._pool = await asyncpg.create_pool(
                    host=os.environ["PGHOST"],
                    port=int(os.environ.get("PGPORT", "5432")),
                    database=os.environ["PGDATABASE"],
                    user=os.environ["PGUSER"],
                    password=token,
                    ssl="require",
                    min_size=2,
                    max_size=10,
                )
            except Exception as e:
                print(f"Lakebase connection failed: {e}")
                self._demo_mode = True
                return None
        return self._pool

    async def refresh_token(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
        await self.get_pool()

    async def start_refresh_loop(self):
        while True:
            await asyncio.sleep(45 * 60)
            try:
                await self.refresh_token()
                print("Token refreshed successfully")
            except Exception as e:
                print(f"Token refresh failed: {e}")

    async def execute(self, query: str, *args):
        pool = await self.get_pool()
        if pool is None:
            return None
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        pool = await self.get_pool()
        if pool is None:
            return []
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        pool = await self.get_pool()
        if pool is None:
            return None
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

db = DatabasePool()
