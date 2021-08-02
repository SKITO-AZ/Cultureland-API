#-*- encoding: utf-8 -*-

from fastapi import BackgroundTasks, Body, FastAPI, Request, Query
from fastapi.responses import ORJSONResponse
from typing import Optional
from datetime import datetime
import cultureland, pymysql, asyncio, jwt, pymongo, time, base64
from setting import *
from models import *

client = pymongo.MongoClient(DB_URL)

db = client[DB_NAME]

log_collection = db[LOG_COLLECTION]
token_collection = db[TOKEN_COLLECTION]
app = FastAPI()

def decode_Token(token):
    try:
        token = base64.urlsafe_b64decode(token)
        token = token.decode('ascii')
        return jwt.decode(token, API_SECRET_KEY, 'HS256')
    except Exception as E:
        return False

@app.get("/api/v2/token", response_class=ORJSONResponse, response_model=TokenResult, responses={
        200: {
            "description": "컬처랜드 아이디와 비밀번호로 토큰 발급",
            "content": {
                "application/json": {
                    "example": {"token": "DISKIOSK API TOKEN"}
                }
            },
        },
    })
async def create_token(request: Request, id: str = Query(
            None,
            title="컬처랜드 아이디",
            description="DISKIOSK API에서 사용하실 컬처랜드 아이디를 입력하여 주세요."
        ),
        pwd : str = Query(
            None,
            title="컬처랜드 비밀번호",
            description="DISKIOSK API에서 사용하실 컬처랜드 비밀번호를 입력하여 주세요."
        )):
    client_host = request.client.host
    token_data = await asyncio.get_event_loop().run_in_executor(None, token_collection.find_one, {'ip' : client_host})
    if token_data == None:
        currenttime = "{:%Y년 %m월 %d일 %H시 %M분 %S초}".format(datetime.now())
        user_data = {
            'ip' : client_host,
            'id' : id,
            'pwd' : pwd
        }
        token = jwt.encode(user_data, API_SECRET_KEY, 'HS256')
        token = base64.urlsafe_b64encode(token)
        post = {
            'ip' : client_host,
            'token_count' : 1,
            'last_edited_time' : currenttime,
            'created_time' : currenttime
        }
        await asyncio.get_event_loop().run_in_executor(None, token_collection.insert_one, post)
        return {'token' : token}
        
    else:
        currenttime = "{:%Y년 %m월 %d일 %H시 %M분 %S초}".format(datetime.now())
        user_data = {
            'ip' : client_host,
            'id' : id,
            'pwd' : pwd
        }
        token = jwt.encode(user_data, API_SECRET_KEY, 'HS256')
        token = base64.urlsafe_b64encode(token)
        filter = { '_id' : token_data['_id'] }
        post = {
            'token_count' : token_data['token_count'] + 1,
            'last_edited_time' : currenttime
        }
        await asyncio.get_event_loop().run_in_executor(None, token_collection.update_one, filter, { '$set' : post })
        return {'token' : token}

@app.get("/api/v2/payments", response_class=ORJSONResponse, response_model=ChargePins, responses={
        200: {
            "description": "DISKIOSK API 토큰으로 컬처랜드 핀 번호 충전",
            "content": {
                "application/json": {
                    'example' : {
                    "결제 성공 시" : {'error' : False, "cash": 5000, 'result' : ['Success']},
                    "이미 등록된 상품권 사용 시" : {'error' : False, "cash": 0, 'result' : ['Expired']},
                    "유효하지 않은 상품권 사용 시" : {'error' : False, "cash": 0, 'result' : ['Invalid']},
                    "10회이상 등록 실패 시" : {'error' : False, "cash": 0, 'result' : ['Limited']},
                    "오류 발생 시" : {'error' : False, "cash": 0, 'result' : ['Error']},
                    "유효하지 않은 토큰 사용 시" : {'error' : True, 'msg' : 'Invalid Token'},
                    "로그인 실패 시" : {'error' : True, 'msg' : 'Login Failed'}}
                }
            },
        },
    })
async def chrage_pin(request: Request, token: str = Query(
            None,
            title="DISKIOSK API 토큰",
            description="발급 받은 토큰을 입력하여 주세요."
        ), pin1: str =Query(
            None,
            title="첫번째 핀번호",
            description="자동 충전 API에서 충전할 상품권의 첫번째 핀번호를 입력하여 주세요."
        ), pin2: str =Query(
            None,
            title="두번째 핀번호",
            description="자동 충전 API에서 충전할 상품권의 두번째 핀번호를 입력하여 주세요."
        ), pin3: str =Query(
            None,
            title="세번째 핀번호",
            description="자동 충전 API에서 충전할 상품권의 세번째 핀번호를 입력하여 주세요."
        ), pin4: str =Query(
            None,
            title="마지막 핀번호",
            description="자동 충전 API에서 충전할 상품권의 마지막 핀번호를 입력하여 주세요."
        )):
    client_host = request.client.host
    if token == None:
        return {'error' : True , 'msg' : 'No Token Data'}

    data = decode_Token(token)
    if data == False:
        return {'error' : True , 'msg' : 'Invalid Token'}

    culture = cultureland.cultureland()
    await asyncio.get_event_loop().run_in_executor(None, culture.login, data['id'], data['pwd'])
    if not await asyncio.get_event_loop().run_in_executor(None, culture.login, data['id'], data['pwd']):
        return JSONResponse({'error' : True, 'msg' : 'Login Failed'})
    result = await asyncio.get_event_loop().run_in_executor(None, culture.charge, [[pin1, pin2, pin3, pin4]])
    currenttime = "{:%Y년 %m월 %d일 %H시 %M분 %S초}".format(datetime.now())
    post = {
        'type' : 'GET',
        'ip' : client_host,
        'token_ip' : data['ip'],
        'culture_id' : data['id'],
        'input_pins' : [[pin1, pin2, pin3, pin4]],
        'result_cash' : result['cash'],
        'result_pins' : result['result'],
        'time_stamp' : currenttime
    }
    await asyncio.get_event_loop().run_in_executor(None, log_collection.insert_one, post)
    return result

@app.post("/api/v2/payments", response_class=ORJSONResponse, response_model=ChargePins, responses={
        200: {
            "description": "DISKIOSK API 토큰으로 컬처랜드 핀 번호 충전",
            "content": {
                "application/json": {
                    "example" : {'결제 성공 시' : {'error' : False, "cash": 15000, 'result' : ['Success', 'Expired', 'Invalid']},
                    "유효하지 않은 토큰 사용 시" : {'error' : True, 'msg' : 'Invalid Token'},
                    "로그인 실패 시" : {'error' : True, 'msg' : 'Login Failed'}}
                }
            },
        },
    })
async def chrage_pins(request: Request, body : ChargePinBody = Body(
        ...,
        example={
            "token": "DISKIOSK API 토큰",
            "pins" : [
                ['1111', '1111', '1111', '1111'],
                ['2222', '2222', '2222', '2222'],
                ['3333', '3333', '3333', '3333']
                ]
        },
    )):
    client_host = request.client.host
    if body.token == None:
        return {'error' : True, 'msg' : 'No Token Data'}
    currenttime = "{:%Y%m%d%H%M%S}".format(datetime.now())
    data = decode_Token(body.token)
    if data == False:
        return {'error' : True , 'msg' : 'Invalid Token'}
    culture = cultureland.cultureland()
    await asyncio.get_event_loop().run_in_executor(None, culture.login, data['id'], data['pwd'])
    if not await asyncio.get_event_loop().run_in_executor(None, culture.login, data['id'], data['pwd']):
        return {'error' : True, 'msg' : 'Login Failed'}
    result = await asyncio.get_event_loop().run_in_executor(None, culture.charge, body.pins)
    currenttime = "{:%Y년 %m월 %d일 %H시 %M분 %S초}".format(datetime.now())
    post = {
        'type' : 'POST',
        'ip' : client_host,
        'token_ip' : data['ip'],
        'culture_id' : data['id'],
        'input_pins' : body.pins,
        'result_cash' : result['cash'],
        'result_pins' : result['result'],
        'time_stamp' : currenttime
    }
    await asyncio.get_event_loop().run_in_executor(None, log_collection.insert_one, post)
    return result
