import asyncio
from database import Db_Connection_Manager
from asyncpg import Connection 
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import math
from typing import Callable, Coroutine, Any

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

@app.middleware('http')
async def check_server_overload(request: fastapi.Request, call_next: Callable[[fastapi.Request], Coroutine[Any, Any, fastapi.Response]]):
    return await call_next(request)

@app.get('/')
async def root(request: fastapi.Request):
    try:
        return {'status':'sucsess'}
    except Exception as e:
        return {'status':'error'}

#root, para debug
@app.get("/busids")
async def listBusIds(request: fastapi.Request):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        try:
            resultado = await c.fetch('SELECT busid FROM buslimeira')
            await asyncio.sleep(4)
            resultado = [linha['busid'] for linha in resultado]#passando para json
            retuning = {'ids':str(resultado)}
        except Exception as e:
            retuning = fastapi.HTTPException(status_code=500,detail=str(e))
    return retuning

@app.get("/udtBusLoc/")
async def udtBusLoc(request: fastapi.Request, busid:int,latitude: float, longitude: float):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
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

def auxNextPosition(center_x:float, center_y:float, prev_x:float, prev_y:float):
    angle = math.atan2(prev_y-center_y, prev_x-center_x)
    radius = math.sqrt((prev_x - center_x)**2 + (prev_y - center_y)**2)
    angle += math.radians(1)
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    new_pos =  (center_x + x, center_y + y)
    return (center_x + x, center_y + y)
    

isMoovingBus200:bool  = False
move_bus_lock = asyncio.Lock()
@app.get("/makeBus200Moove/")
async def makeBus200Moove(request: fastapi.Request):
    #this functions mooves the bus 200 in circles arround plaza españa any bus driver can use it
    global isMoovingBus200
    async with move_bus_lock:
         if isMoovingBus200==True:
            return {"status": "error", "message": "Bus 200 is already moving. Please wait until the current operation completes."}
         isMoovingBus200=True
    center=(41.375053,2.149719)
    actual=(41.375053,2.149140)
    cont_angle = 0
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        try:
            while cont_angle<360:
                print("loc "+ str(actual))
                await c.execute("""UPDATE buslimeira 
                                            SET latitude = $1, 
                                                longitude = $2 
                                            WHERE busid = $3;
                                            """,actual[0], actual[1], 200)
                actual = auxNextPosition(center[0], center[1], actual[0],actual[1])
                await asyncio.sleep(0.1) # 1angle/0.05sec 
                cont_angle+=1
            retuning = {'status':'sucsess'}
        except Exception as e:
            retuning = fastapi.HTTPException(status_code=500,detail=str(e))
        finally:
            isMoovingBus200=False
            return retuning

@app.get("/getBusLoc/")
async def udtBusLoc(request: fastapi.Request,busid:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
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
