from unittest.mock import MagicMock, Mock, patch
from .mock_mongo import MockPyMongo
import json
import sys
import os

### TEST SETUP ###
EXPECTED_DATA_FRAME_FILENAME = os.path.join(os.path.dirname(__file__),
                                          'expected_response.json')
EXPECTED_DATA_FRAME = open(EXPECTED_DATA_FRAME_FILENAME).read()
sys.modules['pymongo'] = MockPyMongo

cloud_mock = MagicMock()
sys.modules['google.cloud'] = cloud_mock
##################

from src.main import _get_data, _refresh_data  # noqa: E402

def test_snapshot():
    expected = _pretty_print(EXPECTED_DATA_FRAME)
    observed = _pretty_print(f'{_get_data().to_json()}')
    assert expected == observed

def test_cold_cache_json():
    _blob().return_value.exists = lambda: False
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data('json')

    find.assert_called_once()

def test_cold_cache_csv():
    _blob().return_value.exists = lambda: False
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data('csv')

    find.assert_called_once()

def test_warm_cache_json():
    _blob().return_value.exists = lambda: True
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data('json')
    find.assert_not_called()

def test_warm_cache_csv():
    _blob().return_value.exists = lambda: True
    _blob().return_value.download_as_string.return_value = '{}'

    find = MockPyMongo.MongoClient().talkspace.messages.find
    find.reset_mock()

    _refresh_data('csv')
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
