from pymongo import MongoClient
import pandas as pd
import re
import textstat
import json
from datetime import date, datetime
from google.cloud import secretmanager
from google.cloud import storage
from flask import jsonify, Response

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
    if request.method == 'OPTIONS':
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*'
    }
    
    data_format = request.args.get('format')

    if not data_format in ['json', 'csv']:
        return "Invalid value for parameter 'format'. Expected 'json' or 'csv'", 422

    if data_format == 'json':
        response = jsonify(_refresh_data(data_format))
    else:
        response = Response(_refresh_data(data_format))
  
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Methods', 'GET')

    return response, 200

def _refresh_data(data_format):
    """Checks cache and returns data
    Args:
        data_format: 'csv' or 'json'
    Returns:
        request object with csv or json of data
    """

    cached_filename = f'{date.today()}.{data_format}'

    if BUCKET.blob(cached_filename).exists():
        bucket_data = BUCKET.blob(cached_filename).download_as_string()

        if data_format == 'json':
            return json.loads(bucket_data)
        else:
            return bucket_data 

    df = _get_data()

    if data_format == 'csv':
        data = df.to_csv(date_format='iso')
        res = data
    else:
       data = df.to_json(orient='records', date_format='iso')
       res = json.loads(data)
  
    BUCKET.blob(cached_filename).upload_from_string(
        data,
        content_type='application/json'
    )
    
    return res


def _get_data(data_format = 'json'):
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

    return message_blocks.drop(['message', 'prev_message'], axis=1)