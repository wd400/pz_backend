from fastapi import FastAPI

from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

import requests
import hashlib

from greens import config
from greens.routers import router as v1
from greens.services.repository import get_mongo_meta,add_prompt,search,get_tag_prompts,list_tags,vote,list_prompts,get_prompt
from greens.utils import get_logger, init_mongo
from pydantic import BaseModel
from typing import List
from fastapi import Response, status
from fastapi import FastAPI, HTTPException

global_settings = config.get_settings()

SALT="ZVOBROFUBZFPCJN"

if global_settings.environment == "local":
    get_logger("uvicorn")

app = FastAPI()


origins = [

    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Settings(BaseModel):
    authjwt_secret_key: str = "PEDXKEPJOHOCIFUNCPDKJ"

# callback to get your configuration
@AuthJWT.load_config
def get_config():
    return Settings()

# exception handler for authjwt
# in production, you can tweak performance using orjson response
@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


#app.include_router(v1, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    app.state.logger = get_logger(__name__)
    app.state.logger.info("Starting greens on your farmland...mmm")
    app.state.mongo_client, app.state.mongo_db, app.state.mongo_collection = await init_mongo(
        global_settings.db_name, global_settings.db_url, global_settings.collection
    )


@app.on_event("shutdown")
async def shutdown_event():
    app.state.logger.info("Parking tractors in garage...")


@app.get("/health-check")
async def health_check():
    return await get_mongo_meta()


class AddPrompt(BaseModel):
    prompt: str
    tags: List[str]
    source: str
    model: str
    output:str

def checklength(data,type_name,max_len):
    if len(data)>max_len:
        raise HTTPException(status_code=403, detail=f"Invalid {type_name} length")


@app.post("/add")
async def add_endpoint(Prompt:AddPrompt):
    checklength(Prompt.prompt,"prompt",500)
    checklength(Prompt.tags,"tags",10)
    checklength(Prompt.source,"source",500)
    checklength(Prompt.model,"model",50)
    checklength(Prompt.output,"output",20_000)
    for tag in Prompt.tags:
        checklength(tag,"tag",20)
        if not tag.isalnum():
            raise HTTPException(status_code=403, detail=f"Tag not alphanum")
    await add_prompt(Prompt)
    return Response(status_code=status.HTTP_200_OK)


class Query(BaseModel):
    query: str
    offset: int


@app.post("/search")
async def search_endpoint(query:Query):
    checklength(query.query,"query",200)
    if query.offset<0:
        raise HTTPException(status_code=403, detail=f"Invalid offset")
    return await search(query)

@app.get("/tags/{offset}")
async def get_tags(offset:int):
    if offset<0:
        raise HTTPException(status_code=403, detail=f"Invalid offset")
    return await list_tags(offset)




class TagQuery(BaseModel):
    order: str
    offset: int

allowed_order={"timestamp","score"}

@app.post("/tag/{tag}")
async def tag_query(tag:str, tag_query: TagQuery ):
    if tag_query.order not in allowed_order:
        raise HTTPException(status_code=403, detail=f"Invalid order") 
    return await get_tag_prompts(tag,tag_query)

class OauthToken(BaseModel):
    token: str

@app.post('/get_token')
def get_token(oauth_token: OauthToken, Authorize: AuthJWT = Depends()):
    #TODO:REGEX for oauth_token
    #TODO: anti ddos
    print(oauth_token.token)
    id=requests.get(f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={oauth_token.token}").json()
    print(id)
    if 'sub' not in id:
        raise HTTPException(status_code=403, detail=f"Invalid token") 
    id=id['sub']

    # subject identifier for who this token is for example id or username from database
    access_token = Authorize.create_access_token(subject=hashlib.sha512((id+ SALT).encode('utf-8')).hexdigest())
    return {"access_token": access_token}




class VoteValue(BaseModel):
    value: int


@app.post("/all")
async def list_all(tag_query: TagQuery ):
    if tag_query.order not in allowed_order:
        raise HTTPException(status_code=403, detail=f"Invalid order") 
    return await list_prompts(tag_query)


@app.get("/prompt/<:promptid>")
async def list_all(promptid:str ):
    return await get_prompt(promptid)



@app.post("/vote/<:promptid>")
async def vote_endpoint(promptid:str,vote_value:VoteValue,Authorize: AuthJWT = Depends()):
    if vote.value not in {-1,1}:
        raise HTTPException(status_code=403, detail=f"Invalid vote value") 
        
    Authorize.jwt_required()
    current_user = Authorize.get_jwt_subject()

    update=await vote(promptid,vote_value.value,current_user)

    return {"update":update}

