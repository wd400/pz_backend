from bson import ObjectId
from pymongo.errors import WriteError
from datetime import datetime
import greens.main as greens
from greens.routers.exceptions import AlreadyExistsHTTPException
from bson.objectid import ObjectId
from fastapi import FastAPI, HTTPException, Depends, Request

async def document_id_helper(document: dict) -> dict:
    document["id"] = document.pop("_id")
    return document


async def retrieve_document(document_id: str, collection: str) -> dict:
    """

    :param document_id:
    :param collection:
    :return:
    """
    document_filter = {"_id": ObjectId(document_id)}
    if document := await greens.app.state.mongo_collection[collection].find_one(document_filter):
        return await document_id_helper(document)
    else:
        raise ValueError(f"No document found for {document_id=} in {collection=}")


async def create_document(document: dict, collection: str) -> dict:
    """

    :param document:
    :param collection:
    :return:
    """
    try:
        document = await greens.app.state.mongo_collection[collection].insert_one(document)
        return await retrieve_document(document.inserted_id, collection)
    except WriteError:
        raise AlreadyExistsHTTPException(f"Document with {document.inserted_id=} already exists")


async def get_mongo_meta() -> dict:
    list_databases = await greens.app.state.mongo_client.list_database_names()
    list_of_collections = {}
    for db in list_databases:
        list_of_collections[db] = await greens.app.state.mongo_client[db].list_collection_names()
    mongo_meta = await greens.app.state.mongo_client.server_info()
    return {"version": mongo_meta["version"], "databases": list_databases, "collections": list_of_collections}


async def add_prompt(prompt_request):
    
    collection = greens.app.state.mongo_client['DB']['new_prompts']
    new_document = {"prompt": prompt_request.prompt,
                    "tags": [t.lower() for t in prompt_request.tags],
                    "source":prompt_request.source,
                    "model":prompt_request.model,
                    "description":prompt_request.description,
                    "output":prompt_request.output,
                    "timestamp":datetime.now().timestamp()}
    document_id = await collection.insert_one(new_document)
    print(f"Document was successfully inserted with id: {document_id}")

def convert_objectid(l):
    for item in l:
        item['_id']=str(item['_id'])

async def search(query_request):
    collection = greens.app.state.mongo_client['DB']['prompts']

    search_query = {"$text":{"$search":query_request.query}}
    #limit(30)
    l=await collection.find(search_query).skip(query_request.offset).to_list(30)
    convert_objectid(l)
    return l


async def list_prompts(req):
    collection = greens.app.state.mongo_client['DB']['prompts']
    #limit(30)
    l= await collection.find().sort(req.order, -1).skip(req.offset).to_list(30)
    convert_objectid(l)
    return l

async def list_tags(offset):
    collection = greens.app.state.mongo_client['DB']['tags']
    #limit(30)
    l= await collection.find().sort('score', -1).skip(offset).to_list(100)
    convert_objectid(l)
    print(l)
    return l

async def get_prompt(prompt_id):
    l= await greens.app.state.mongo_client['DB']['prompts'].find_one({'_id':ObjectId(prompt_id)})
    if l:
        del l['_id']
    return l


async def get_tag_prompts(tag,tag_prompt):
    collection = greens.app.state.mongo_client['DB']['prompts']
    search_query = { "tags": { "$in": [ tag] } }
    #limit(30)
    l= await collection.find(search_query).sort(tag_prompt.order, -1).skip(tag_prompt.offset).to_list(30)
    convert_objectid(l)
    return l

async def fn_vote(prompt_id,vote,user_id):
    print("new_vote",vote)
    async with await greens.app.state.mongo_client.start_session() as s:
        # Note, start_transaction doesn't require "await".
        async with s.start_transaction():
            prompts = greens.app.state.mongo_client['DB']['prompts']
            print("prompt_id",prompt_id)
            prompt_id=ObjectId(prompt_id)
            if await prompts.find_one({'_id':prompt_id}, session=s):
                votes = greens.app.state.mongo_client['DB']['votes']
                previous_vote= await votes.find_one({'prompt_id':prompt_id,'user':user_id}, session=s)
                print("previous_vote",previous_vote)
                if previous_vote:
                    previous_vote=previous_vote['value']
                    if previous_vote==vote:
                        raise HTTPException(status_code=403, detail=f"You already voted") 
                    else:
                        await votes.update_one({'prompt_id':prompt_id,'user':user_id},{'$set': {'value': vote}}, session=s)
                        update=vote-previous_vote
                else:
                    await votes.insert_one({'prompt_id':prompt_id,'user':user_id,'value':vote}, session=s)
                    update=vote
                print("update",update)
                await prompts.update_one({'_id':prompt_id},{'$inc':{"score":update}}, session=s)
            else:
                raise HTTPException(status_code=404, detail=f"Prompt not found") 

    return update