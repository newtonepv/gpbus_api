import asyncio
from database import Db_Connection_Manager
from asyncpg import Connection 
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


db = Db_Connection_Manager()
#funcao parametro que define o que acontece antes e depois de criar a api
@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    await db.init_pool()
    yield 
    await db.close_pool()

app = fastapi.FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

#root, para debug
@app.get("/busids")
async def listBusIds():
    async for c in db.get_connection():#apenas uma, mas é pra usar o yield no async with
        try:
            resultado = await c.fetch('SELECT busid FROM buslimeira')
            resultado = [linha['busid'] for linha in resultado]#passando para json
            retuning = {'ids':str(resultado)}
        except Exception as e:
            retuning = fastapi.HTTPException(status_code=500,detail=str(e))
    return retuning

@app.get("/udtBusLoc/")
async def udtBusLoc(busid:int,latitude: float, longitude: float):
    async for c in db.get_connection():#apenas uma, mas é pra usar o yield no async with
        try:
            await c.execute("""UPDATE buslimeira 
                                        SET latitude = $1, 
                                            longitude = $2 
                                        WHERE busid = $3;
                                        """,latitude, longitude, busid)
            retuning = {'status':'sucsess'}
        except Exception as e:
            retuning = fastapi.HTTPException(status_code=500,detail=str(e))
    return retuning

@app.get("/getBusLoc/")
async def udtBusLoc(busid:int):
    async for c in db.get_connection():#apenas uma, mas é pra usar o yield no async with
        try:
            resultado = await c.fetchrow("""SELECT latitude, longitude
                                        FROM buslimeira
                                        WHERE busid = $1;
                                        """, busid)
            if resultado:
                retuning = {
                    'latitude': resultado['latitude'],
                    'longitude': resultado['longitude']
                }
            else:
                retuning = {'error': 'Bus not found'}
        except Exception as e:
            retuning = fastapi.HTTPException(status_code=500,detail=str(e))
    return retuning
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)