from pymongo import MongoClient
import pandas as pd
import re
import textstat
from datetime import datetime

def _access_secret_version(project_id, secret_id, version_id='latest'):
    """
    Access the payload for the given secret version if one exists. The version
    can be a version number as a string (e.g. "5") or an alias (e.g. "latest").
    """

    # Import the Secret Manager client library.
    from google.cloud import secretmanager

    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # Access the secret version.
    response = client.access_secret_version(request={"name": name})

    # Print the secret payload.
    #
    # WARNING: Do not print the secret in a production environment - this
    # snippet is showing how to access the secret material.
    return response.payload.data.decode("UTF-8")


MONGO_CONNECTION_STRING = _access_secret_version(
    'talkspace-293821', 'MONGO_CONNECTION_STRING')

last_cache_refresh = datetime.now()

cached_response = None


def get_data(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    request_json = request.get_json()
    if request.args and 'message' in request.args:
        return request.args.get('message')
    elif request_json and 'message' in request_json:
        return request_json['message']
    else:
        return _get_data()


# Private


def _get_data():
    cache_age = (last_cache_refresh - datetime.now()) / datetime.timedelta(hours=1)  # noqa: F823

    if cached_response and cache_age < 6:
        return cached_response  # noqa: F823

    last_cache_refresh = datetime.now()  # noqa: F841

    # Other message types include automated messages from Talkspace
    RELEVANT_MESSAGE_TYPES = [1]

    messages = pd.DataFrame([
        *MongoClient(MONGO_CONNECTION_STRING).talkspace.messages.find(
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
        messages.user_id.shift()).cumsum()

    message_blocks = messages.groupby(message_block_index).agg({
        'message': lambda l: '\n'.join(l),
        'created_at': min,
        'display_name': 'first'
    })

    message_blocks['message_length'] = message_blocks.message.apply(len)
    message_blocks['question_count'] = message_blocks.message.apply(
        lambda x: len(re.findall(r'\?', x)))
    message_blocks['word_count'] = message_blocks.message.apply(
        lambda x: len(re.findall(r'\s', x)) + 1)
    message_blocks['readability'] = message_blocks.message.apply(
        textstat.flesch_reading_ease)

    message_blocks = pd.concat(
        [message_blocks, message_blocks.shift().add_prefix('prev_')], axis='columns')

    # There are the quantities I'm interested in improving
    message_blocks['response_time'] = (
        message_blocks.created_at - message_blocks.prev_created_at) / pd.Timedelta(days=1)
    message_blocks['words_per_day'] = message_blocks['word_count'] / \
        message_blocks['response_time']

    message_blocks.dropna(inplace=True)
    cached_response = message_blocks.drop(['message', 'prev_message'], axis=1).head(
    ).to_json(orient='records', date_format='iso')
    return cached_response
