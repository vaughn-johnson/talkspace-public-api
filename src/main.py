from pymongo import MongoClient
import pandas as pd
import re
import textstat
import json
from datetime import date, datetime
from google.cloud import secretmanager
from google.cloud import storage
from flask import jsonify

# Get mongo connection string
PROJECT_ID = 'talkspace-293821'
SECRET_ID = 'MONGO_CONNECTION_STRING'
SECRETS_CLIENT = secretmanager.SecretManagerServiceClient()
name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
response = SECRETS_CLIENT.access_secret_version(request={"name": name})

# Initialize mongo client
MONGO_CONNECTION_STRING = response.payload.data.decode('UTF-8')
MONGO_CLIENT = MongoClient(MONGO_CONNECTION_STRING).talkspace.messages

# Intialize storage client
STORAGE_CLIENT = storage.Client()
BUCKET = STORAGE_CLIENT.bucket('vaughn-public-talksapce-data')

def refresh_data(request):
    return jsonify(_refresh_data())

def _refresh_data():
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    cached_filename = f'{date.today()}.json'

    if BUCKET.blob(cached_filename).exists():
        bucket_data = BUCKET.blob(cached_filename).download_as_string()
        return json.loads(bucket_data)

    data = _get_data()
    BUCKET.blob(cached_filename).upload_from_string(
        json.dumps(data),
        content_type='application/json'
    )
    return data


def _get_data():
    # Other message types include automated messages from Talkspace
    RELEVANT_MESSAGE_TYPES = [1]

    messages = pd.DataFrame([
        *MONGO_CLIENT.find(
            {'message_type': {'$in': RELEVANT_MESSAGE_TYPES}}
        )
    ])

    messages.created_at = messages.created_at.apply(pd.to_datetime)

    # I tend to quote my therapist and then delimit the beginning of my own
    # words using a ">"
    #
    # Dallas tends to begin his messages with "Vaughn,"
    # and ends them with "Respectfully, Dallas"
    #
    # Dallas: Vaughn,
    #         lorem ipsum lakdfj
    #         Respectfully, Dallas
    #
    # Vaughn: "lorem ipsum lakdfj"
    #         > abalksjfd
    #
    ARROW_DELIMITER = re.compile('[^-]> ')
    EXTRATA = re.compile('(Vaughn,\n*|Respectfully,\n\nDallas)')
    REPEAT_NEWLINES = re.compile('\n\n+')

    def extract_my_words(msg):
        if not ARROW_DELIMITER.match(msg):
            return msg

        return ''.join(re.split(ARROW_DELIMITER, msg))[1:]

    def process_message(msg):
        msg = extract_my_words(msg)
        msg = re.sub(EXTRATA, '', msg)
        msg = re.sub(REPEAT_NEWLINES, '\n', msg)
        return msg

    messages.message = messages.message.apply(process_message)

    # This is critical for rest of the analysis
    messages.sort_values('created_at', axis='rows', inplace=True)

    # This associates consecutive messages (in time) from the same person
    message_block_index = messages.user_id.ne(
        messages.user_id.shift()
    ).cumsum()

    message_blocks = messages.groupby(message_block_index).agg({
        'message': lambda l: '\n'.join(l),
        'created_at': min,
        'display_name': 'first'
    })

    message_blocks['message_length'] = message_blocks.message.apply(len)

    message_blocks['question_count'] = message_blocks.message.apply(
        lambda x: len(re.findall(r'\?', x))
    )

    message_blocks['word_count'] = message_blocks.message.apply(
        lambda x: len(re.findall(r'\s', x)) + 1
    )

    message_blocks['readability'] = message_blocks.message.apply(
        textstat.flesch_reading_ease
    )

    shifted_messages = message_blocks.shift().add_prefix('prev_')

    message_blocks = pd.concat(
        [message_blocks, shifted_messages],
        axis='columns'
    )

    # There are the quantities I'm interested in improving
    message_blocks['response_time'] = (
        message_blocks.created_at - message_blocks.prev_created_at) / pd.Timedelta(days=1)
    message_blocks['words_per_day'] = message_blocks['word_count'] / \
        message_blocks['response_time']

    message_blocks.dropna(inplace=True)
    formatted_response = message_blocks.drop(['message', 'prev_message'], axis=1).to_json(orient='records', date_format='iso')
    return json.loads(formatted_response)
