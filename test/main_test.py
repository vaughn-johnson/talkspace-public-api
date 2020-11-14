from unittest.mock import MagicMock
from .mock_mongo import MockPyMongo
import json
import sys
import os

EXPECTED_RESPONSE_FILENAME = os.path.join(os.path.dirname(__file__),
                                          'expected_response.json')
EXPECTED_RESPONSE = open(EXPECTED_RESPONSE_FILENAME).read()
sys.modules['pymongo'] = MockPyMongo
sys.modules['google.cloud'] = MagicMock()

from src.main import _get_data  # noqa: E402

def test_snapshot():
    expected = _pretty_print(EXPECTED_RESPONSE)
    observed = _pretty_print(f'{_get_data()}')
    assert expected == observed

def _pretty_print(json_string):
    json.dumps(
        json.loads(json_string),
        indent=2,
        sort_keys=True
    )
