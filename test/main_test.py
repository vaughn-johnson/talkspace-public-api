from unittest.mock import MagicMock, Mock, patch
from .mock_mongo import MockPyMongo
import json
import sys
import os

### TEST SETUP ###
EXPECTED_RESPONSE_FILENAME = os.path.join(os.path.dirname(__file__),
                                          'expected_response.json')
EXPECTED_RESPONSE = open(EXPECTED_RESPONSE_FILENAME).read()
sys.modules['pymongo'] = MockPyMongo

cloud_mock = MagicMock()
sys.modules['google.cloud'] = cloud_mock
##################

from src.main import _get_data, _refresh_data  # noqa: E402

def test_snapshot():
    expected = _pretty_print(EXPECTED_RESPONSE)
    observed = _pretty_print(f'{json.dumps(_get_data())}')
    assert expected == observed

def test_cold_cache():
    _blob().return_value.exists = lambda: False
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data()

    find.assert_called_once()

def test_warm_cache():
    _blob().return_value.exists = lambda: True
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data()
    find.assert_not_called()

def _pretty_print(json_string):
    json.dumps(
        json.loads(json_string),
        indent=2,
        sort_keys=True
    )

def _blob():
    return cloud_mock.storage\
                     .Client.return_value\
                     .bucket.return_value\
                     .blob
