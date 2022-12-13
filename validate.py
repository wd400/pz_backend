from pymongo import MongoClient
import sys
import os
from bson.objectid import ObjectId

prompt_id=sys.argv[1]

client = MongoClient('mongodb:27017',
                     username="farmer",#os.getenv("MONGO_USER", ""),
                     password="tractor",#os.getenv("MONGO_PASS", "")
                     )
db = client['DB']
source_coll = db['new_prompts']
dest_coll = db['prompts']
with client.start_session() as session:
    with session.start_transaction():
        doc = source_coll.find_one({'_id': ObjectId(prompt_id)},session=session)
        source_coll.delete_one({'_id': ObjectId(prompt_id)},session=session)
        
        doc['score']=0
        del doc['_id']
        print(doc)
        for tag in doc['tags']:
            db['tags'].update_one({'name': tag}, {'$inc': {"score":1}} ,upsert=True,session=session)

        dest_coll.insert_one(doc,session=session)




client.close()