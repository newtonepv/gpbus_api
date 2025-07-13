import asyncio
from database import Db_Connection_Manager
from asyncpg import Connection
import asyncpg 
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import math
from typing import Callable, Coroutine, Any
from bus200SimulatedStepsFile import bus200SimulatedSteps
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
    #implement api overload instead of just database overload (requests/second)
    return await call_next(request)

#root, para debug
@app.get('/')
async def root(request: fastapi.Request):
    try:
        return {'status':'sucsess'}
    except Exception as e:
        return {'status':'error'}

@app.get("/busids")
async def busids(request: fastapi.Request):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        resultado = await c.fetch('SELECT busid FROM buslimeira')
        resultado = [linha['busid'] for linha in resultado]#passando para json
        return {'ids':str(resultado)}
    
@app.get("/getBusRoute/")
async def getBusRoute(request: fastapi.Request, busid:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        resultado = await c.fetchrow('SELECT route FROM buslimeira WHERE busid=$1',busid)
        resultado = [resultado[0]]#passando para json
        return {'route':str(resultado)}
        
        
async def autenthicate_driver_aux(c:Connection, driverId: int, driverPassword: str)->bool:
    response = await c.execute("""SELECT id 
                            FROM driverslimeira 
                            WHERE id = $1 AND password = $2;
                        """,driverId, driverPassword)
    return response=="SELECT 1"

@app.get("/authenticateDriver/")
async def authenticateDriver(request: fastapi.Request, driverId: int, driverPassword: str):
    async for c in db.get_connection(request.client.host):
        respostaDoBd = str(await autenthicate_driver_aux(c,driverId,driverPassword))
        return {"hasAccess": respostaDoBd}
        
    
async def autenthicate_passanger_aux(c:Connection, userName: str, driverPassword: str)->bool:
    response = await c.execute("""SELECT username 
                            FROM passanger 
                            WHERE username = $1 AND password = $2;
                        """,userName, driverPassword)
    return response=="SELECT 1"

@app.get("/authenticatePassanger/")
async def authenticatePassanger(request: fastapi.Request, userName: str, userPassword: str):
    
    async for c in db.get_connection(request.client.host):
        respostaDoBd = str(await autenthicate_passanger_aux(c,userName,userPassword)); 
        return {"hasAccess": respostaDoBd}
        
@app.get("/createPassanger/")
async def createPassanger(request: fastapi.Request, userName: str, userPassword: str):
    print("userName =" +userName + " userPassword = "+ userPassword)
    async for c in db.get_connection(request.client.host):
        try:
            await c.execute("""INSERT INTO passanger
                            VALUES ($1, $2)""", userName, userPassword)
            
            return {"status": "success"}

        except asyncpg.exceptions.UniqueViolationError as e:
            #in case the username already exists
            raise fastapi.HTTPException(409,detail="This username already exists")
      
@app.get("/udtBusLoc/")
async def udtBusLoc(request: fastapi.Request, busid:int,latitude: float, longitude: float, idDriver: int, driverPassword: str):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        #verify if the request comes from the true driver and not domebody trying to moove the bus
        if(await autenthicate_driver_aux(c,idDriver, driverPassword)==False):
            #no need to handle this in the app, its just for security, in the app you can only make this request if you are logged
            raise fastapi.HTTPException(status_code=401,detail="Wrong bus driver password")
        else:
            #verify if the bus driver can drive this bus
            response = await c.fetchval("""SELECT EXISTS (
                            SELECT 1 
                            FROM busdriverassignment 
                            WHERE driverid = $1 AND busid = $2
                        ) AS pode_dirigir;""",idDriver, busid)
            if(response == False):
                print("nao pode")
                raise fastapi.HTTPException(status_code=401,detail="This bus driver cant drive this bus")
            else:
                await c.execute("""UPDATE buslimeira 
                                            SET latitude = $1, 
                                                longitude = $2 
                                            WHERE busid = $3;
                                            """,latitude, longitude, busid)
                returning = {'status':'sucsess'}
    print("returning.type=" +str(type(returning)))
    return returning


    

isMoovingBus200:bool  = False
move_bus_lock = asyncio.Lock()
@app.get("/makeBus200Moove/")
async def makeBus200Moove(request: fastapi.Request):
    #this functions mooves the bus 200 in circles arround plaza españa any bus driver can use it
    
    global isMoovingBus200
    async with move_bus_lock:
         if isMoovingBus200==True:
            raise fastapi.HTTPException(status_code=409, detail="Bus 200 is already moving. Please wait until the current operation completes.")
         isMoovingBus200=True

    #apenas uma, mas é pra usar o yield no async with
    asyncio.create_task(makeBus200MooveCoroutine(request)) 
    retuning = {'status':'sucsess'}
    return retuning

async def makeBus200MooveCoroutine(request: fastapi.Request):
    async for c in db.get_connection(request.client.host):
        cont = 0
        while cont<len(bus200SimulatedSteps):
            actual = bus200SimulatedSteps[cont]
            await c.execute("""UPDATE buslimeira 
                                        SET latitude = $1, 
                                            longitude = $2 
                                        WHERE busid = $3;
                                        """,actual[0], actual[1], 200)
            await asyncio.sleep(0.1) # 1angle/0.05sec 
            cont+=1
        global isMoovingBus200
        isMoovingBus200=False

@app.get("/getBusLoc/")
async def udtBusLoc(request: fastapi.Request,busid:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
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
    return retuning
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
