from motor.motor_asyncio import AsyncIOMotorClient

def create_mongo_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri)
