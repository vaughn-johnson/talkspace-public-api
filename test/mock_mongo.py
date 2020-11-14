from unittest.mock import MagicMock
import json
import os

MONGO_MOCK_FILENAME = os.path.join(os.path.dirname(__file__),
                                   'mock_mongo_response.json')

mock_messages = json.loads(open(MONGO_MOCK_FILENAME).read())
MockPyMongo = MagicMock()
MockPyMongo.MongoClient.return_value.talkspace.messages.find.return_value = mock_messages
