import os
from dotenv import load_dotenv
import contextlib
import asyncpg
import fastapi
import typing

load_dotenv()
db_url = os.getenv("DATABASE_URL")

#singleton_class
class Db_Connection_Manager:
    #static variables
    _instance = None
    _pool : asyncpg.Pool = None
    def __new__(singleton):
        if (singleton._instance == None):
            singleton._instance = super().__new__(singleton)
            return singleton._instance
        
    async def init_pool(self):#passar para aenter e aexit
        if(self._pool is None):
            self._pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=15,
            )
        
    async def close_pool(self):#passar para aenter e aexit
        if self._pool:
            await self._pool.close()
            self._pool=None
        
    async def get_connection(self) -> typing.AsyncGenerator[asyncpg.connection.Connection, None]:
        if self._pool:
            async with self._pool.acquire() as con:
                print("started connection")
                yield con #quando a função que chamou acabar, é chamado o __aexit__ de "con" para que seja fechado
                print("returned connection to pool")