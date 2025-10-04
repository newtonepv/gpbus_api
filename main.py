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
from datetime import datetime
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

    
async def autenthicate_passanger_aux(c:Connection, userName: str, userPassword: str)->bool:
    response = await c.execute("""SELECT username 
                            FROM passanger 
                            WHERE username = $1 AND password = $2;
                        """,userName, userPassword)
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

@app.get("/getBusRoute/")
async def getBusRoute(request: fastapi.Request, busid:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        resultado = await c.fetchrow('SELECT route FROM buslimeira WHERE busid=$1',busid)
        resultado = [resultado[0]]#passando para json
        return {'route':str(resultado)}
    
def count_likes_aux(c_likes:list[asyncpg.Record]):
    n_likes:int = 0
    n_dislikes:int = 0
    for l in c_likes:
        if bool(l[0]):
            n_dislikes+=1
        else:
            n_likes+=1
    return n_likes,n_dislikes

@app.get("/getBusComments/")
async def getBusComments(request: fastapi.Request, busid:int):
    print("getBusComments busid"+str(busid))
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        bus_comments = await c.fetch('SELECT (comment_id, comment_content, stars, user_name, comment_time) FROM comments WHERE bus_id=$1',busid)
        #using a dictionary instead of creating a class
        dict_comments_list:list[dict] = []

        #initialize dict
        for comment in bus_comments:
            new_comment = dict()
            new_comment['id'] = int(comment[0][0])
            new_comment['message'] = str(comment[0][1])
            new_comment['stars'] = int(comment[0][2])
            new_comment['userName'] = str(comment[0][3])
            new_comment['date'] = datetime.fromisoformat(str(comment[0][4]))
            dict_comments_list.append(new_comment)


        for dict_comment in dict_comments_list:
            id:int = dict_comment['id']
            #searching for the likes and dislikes
            c_likes= await c.fetch('SELECT (is_dislike) FROM likes WHERE comment_id=$1',id)
            dict_comment['likes'], dict_comment['dislikes'] = count_likes_aux(c_likes)

        return dict_comments_list

@app.get("/likeComment/")
async def likeComment(request: fastapi.Request, commentId:int, userName:str, interactionCode:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        if(interactionCode!=0):
            isDislike=(interactionCode==-1)
            try:
                await c.execute('INSERT INTO likes (user_name, comment_id, is_dislike) VALUES ($1, $2, $3)',userName,commentId,isDislike)
            except asyncpg.exceptions.UniqueViolationError as e:
                await c.execute('UPDATE likes SET is_dislike=$1 WHERE comment_id=$2 AND user_name=$3',isDislike,commentId,userName)
        else:
            await c.execute('DELETE from likes WHERE comment_id=$1 AND user_name=$2', commentId,userName)

@app.get("/addBusComment/")
async def addBusComment(request: fastapi.Request, busid:int, userName:str, userPassword:str, comment:str, stars:int):
    async for c in db.get_connection(request.client.host):#apenas uma, mas é pra usar o yield no async with
        hasAccess = await autenthicate_passanger_aux(c,userName,userPassword)

        if(hasAccess==False):
            raise fastapi.HTTPException(status_code=401, detail="You are not logged")
        else:
            try:
                await c.execute('INSERT INTO comments (comment_content, stars, user_name, bus_id, comment_time) VALUES ($1, $2, $3, $4, NOW())',comment,stars,userName,busid)
                return {'status':"success"}
            #no need to handle thoose in the app, they should not happen there
            except asyncpg.exceptions.ForeignKeyViolationError as e:
                return {'status':'error', 'error_message':str(e)}
            except asyncpg.exceptions.CheckViolationError as e:
                return {'status':'error', 'error_message':str(e)}
            
@app.get("/checkIfUserLikedComment/")
async def checkIfUserLikedComment(request: fastapi.Request, commentId:int, userName:str):
    async for c in db.get_connection(request.client.host):#apenas uma connection, mas é pra usar o yield no async with
        result = await c.fetchrow("""SELECT 
                        CASE 
                            WHEN EXISTS (
                                SELECT 1 
                                FROM likes 
                                WHERE user_name = $1
                                AND comment_id = $2
                            ) THEN (
                                SELECT is_dislike 
                                FROM likes 
                                WHERE user_name = $1 
                                AND comment_id = $2
                            )
                            ELSE NULL
                        END AS is_dislike,
                        EXISTS (
                            SELECT 1 
                            FROM likes 
                            WHERE user_name = $1 
                            AND comment_id = $2
                        ) AS exists_like;""",userName,commentId)
        return result #retorna duas colunas, uma informando se tem uma reação, e outra informando se é um dislike

@app.get("/createAlarm/")
async def createAlarm(request: fastapi.Request, username: str, password: str, busid: int, start_time: str, end_time: str, c_latitude: float, c_longitude: float, c_radius: float):
    formato = "%H:%M:%S"
    s = None  # late
    e = None  # late
    
    try:
        s = datetime.strptime(start_time, formato)
        e = datetime.strptime(end_time, formato)
        if(s > e):
            raise fastapi.HTTPException(status_code=400, detail="hora inválida")
    except ValueError as e:
        raise fastapi.HTTPException(status_code=400, detail="hora inválida")
    
    async for c in db.get_connection(request.client.host):
        try:
            
            user_check = await c.fetchrow("""
                SELECT username FROM passanger 
                WHERE username = $1 AND password = $2;
                """, username, password)
            
            if not user_check:
                raise fastapi.HTTPException(status_code=401, detail="Credenciais inválidas")
            
            await c.execute("""
                INSERT INTO alarms (username, busid, start_time, end_time, c_latitude, c_longitude, c_radius)
                VALUES ($1,$2,$3,$4,$5,$6,$7);
                """, username, busid, s, e, c_latitude, c_longitude, c_radius)
            
            return {'status': 'success', 'message': 'Alarme criado com sucesso'}
            
        except asyncpg.exceptions.ForeignKeyViolationError as e:
            return {'status': 'error', 'error_message': str(e)}
        except asyncpg.exceptions.CheckViolationError as e:
            return {'status': 'error', 'error_message': str(e)}


@app.get("/getAlarms/")
async def getAlarms(request: fastapi.Request, username: str):
    async for c in db.get_connection(request.client.host):
        try:
            result = await c.fetch("""
                SELECT alarm_id, username, busid, start_time, end_time, c_latitude, c_longitude, c_radius
                FROM alarms 
                WHERE username = $1
                ORDER BY start_time;
                """, username)
            
            # Convert the result to a list of dictionaries for JSON response
            alarms = []
            for row in result:
                alarm = {
                    'alarm_id': row['alarm_id'],
                    'username': row['username'],
                    'busid': row['busid'],
                    'start_time': row['start_time'].strftime("%H:%M:%S"),
                    'end_time': row['end_time'].strftime("%H:%M:%S"),
                    'c_latitude': row['c_latitude'],
                    'c_longitude': row['c_longitude'],
                    'c_radius': row['c_radius']
                }
                alarms.append(alarm)
            
            return {'status': 'success', 'alarms': alarms}
            
        except asyncpg.exceptions.PostgresError as e:
            return {'status': 'error', 'error_message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_message': f'Unexpected error: {str(e)}'}


@app.get("/deleteAlarm/")
async def deleteAlarm(request: fastapi.Request, username: str, password: str, alarm_id: int):
    async for c in db.get_connection(request.client.host):
        user_auth = await c.fetchrow("""
            SELECT username FROM passanger 
            WHERE username = $1 AND password = $2;
            """, username, password)
        
        if not user_auth:
            raise fastapi.HTTPException(status_code=401, detail="Usuário inválidas")
        
        alarm_check = await c.fetchrow("""
            SELECT alarm_id FROM alarms 
            WHERE alarm_id = $1 AND username = $2;
            """, alarm_id, username)
        
        if not alarm_check:
            raise fastapi.HTTPException(status_code=404, detail="Alarme não encontrado ou não pertence ao usuário")
        
        result = await c.execute("""
            DELETE FROM alarms 
            WHERE alarm_id = $1 AND username = $2;
            """, alarm_id, username)
        
        if result == "DELETE 0":
            return {'status': 'error', 'error_message': 'Nenhum alarme foi removido'}
        return {'status': 'success', 'message': 'Alarme removido com sucesso'}
            


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
