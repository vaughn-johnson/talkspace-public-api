# talkspace-public-api
![Lint And Test](https://github.com/vaughn-johnson/talkspace-public-api/workflows/Lint%20and%20Test/badge.svg)
![Codecov](https://img.shields.io/codecov/c/github/vaughn-johnson/talkspace-public-api)

A public API hosted on Google Cloud Functions that returns some select features of all the messages exchanged between me and my therapist.

Available [here](https://us-central1-talkspace-293821.cloudfunctions.net/talkspace-public-api?format=csv). Results are cached daily

The observational unit here has been changed from individual messages to blocks of messages sent by the same person. The messages were concatenated, the `created_at` time was taken to be the first of the block.

|column|description|
|---|---|
|created_at|ISO timestamp when message was sent in UTC|
|display_name|The name of the person sending the message. My name is Vaughn and my Therapist's name is Dallas|
|message_length|The number of characters in the particular message|
|prev_created_at|ISO timestamp when the previous person sent a message in UTC|
|prev_display_name|The display name this block of messages is responding to.|
|prev_readability|The [Flesch](https://www.wikiwand.com/en/Flesch%E2%80%93Kincaid_readability_tests#/Flesch_reading_ease) reading ease score of the previous block of messages. Higher scores mean easier to read|
|prev_word_count|The number of values delimited by whitespace in the previous message block|
|question_count|The number of times "?" appears in the previous message block|
|readability|The [Flesch](https://www.wikiwand.com/en/Flesch%E2%80%93Kincaid_readability_tests#/Flesch_reading_ease) reading ease score of the previous block of messages. Higher scores mean easier to read|
|response_time|The time between when the previous and current messages blocks were created. In units of 24 hours|
|word_count|The number of values delimited by whitespace in the current message block|
|words_per_day|The `word_count / response_time`| 
