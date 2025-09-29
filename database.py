import os
from dotenv import load_dotenv
import asyncpg
import asyncio
import fastapi
import typing
from collections import defaultdict

MAX_CONNECTIONS_FOR_IP = 4

load_dotenv()
db_url = os.getenv("DATABASE_URL")
class Db_Connection_Manager:
    _instance = None
    _pool: asyncpg.Pool = None
    _connections: dict[str, int] = {}
    _ip_locks: dict[str, asyncio.Lock] = {}
    _global_lock = asyncio.Lock()  # Para operações globais no pool, e para limitar a conexões sem execões
    _num_active_connections=0    

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    async def init_pool(self):
        async with self._global_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    db_url,
                    min_size=1,
                    max_size=15,
                )
        
    async def close_pool(self):
        async with self._global_lock:
            if self._pool:
                await self._pool.close()
                self._pool = None
        
    def is_full(self) -> bool:
        return self._num_active_connections > (self._pool._maxsize * 0.8)

    async def get_connection(self, client_ip: str) -> typing.AsyncGenerator[asyncpg.connection.Connection, None]:
        
        if not self._pool:
            raise fastapi.HTTPException(status_code=500, detail="Database pool not initialized")

        # lock global é usado para que não sejam feitos vários locks locais para um mesmo ip
        async with self._global_lock:
            if(self._num_active_connections>=self._pool._maxsize):
                print("[ERROR] self._num_active_connections>=self._pool._maxsize")
                raise fastapi.HTTPException(status_code=502, detail="Server overload")
            print("[INFO] "+client_ip+" request passed max connections check, "+str(self._num_active_connections)+"<"+str(self._pool._maxsize))
            self._num_active_connections+=1
            if client_ip not in self._ip_locks:
                self._ip_locks[client_ip] = asyncio.Lock()
            ip_lock = self._ip_locks[client_ip]

        # esse lock é para todas as threads com o mesmo 'client_ip' 
        async with ip_lock:
            #esse trecho de código controla as conexões de cada ip
            if client_ip not in self._connections:
                #print(f"IP {client_ip} passed max connections test")
                self._connections[client_ip] = 1
            else:
                if self._connections[client_ip] >= MAX_CONNECTIONS_FOR_IP:
                    self._num_active_connections-=1
                    print("Too many connections for this IP")
                    raise fastapi.HTTPException(
                        status_code=429, 
                        detail="Too many connections for this IP"
                    )
                #print(f"IP {client_ip} passed max connections test")
                self._connections[client_ip] += 1
            #print(f"IP {client_ip} now has {self._connections[client_ip]} connections")

        

        '''async with com yield é pro seguinte, o yield deixa que quem chamou get_connection()
         a use, quando começa, o método da classe connection inicializa ela, quando termina,
         fecha automaticamnete 
        '''
        async with self._pool.acquire() as con:
            try:
                yield con
            finally:
                async with ip_lock:#bloqueia as outras tasks com o mesmo ip para resolver o problema da corrida
                    if self._connections[client_ip] == 1:
                        # Libera a memória dos diccionarios se o ip não tem mais conexões, seria ideal por isso em aexit do Connection
                        del self._connections[client_ip]
                        del self._ip_locks[client_ip]
                    else:
                        self._connections[client_ip] -= 1
                    #print(f"IP {client_ip} released a connection")
                
                self._num_active_connections-=1