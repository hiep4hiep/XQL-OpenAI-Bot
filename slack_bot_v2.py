from dotenv import load_dotenv
from slack_sdk import WebClient
from flask import Flask, request, jsonify, render_template
from slackeventsapi import SlackEventAdapter
import os
import openai
from openai.embeddings_utils import get_embedding
import pandas as pd
import numpy as np
import json
import uuid

load_dotenv()
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SIGNING_SECRET = os.getenv('SIGNING_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Init Flask endpoint
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(SIGNING_SECRET, '/slack/events', app)
client = WebClient(token=SLACK_TOKEN)

# Init
openai.api_key = OPENAI_API_KEY
context_instruction_limit = 12
terminator = "\n\n"
EMBEDDING_MODEL_NAME = "curie"
input_datapath = './instruction_query_pairs_embeddings.csv'
df = pd.read_csv(input_datapath, header=0)


# Creates a numerical score indicating how similar 2 text phrases are
# Requires the embedding of both text phrases
def vector_similarity(x: list, y: list):
    dot = np.dot(np.array(x), np.array(y))
    return dot


# Given the users question/instruction, generate the context in conversation format
def generate_context(question):
    embedding = get_embedding(question, engine=f"text-search-{EMBEDDING_MODEL_NAME}-doc-001")
    distance_list = df.copy(deep=True)
    distance_list['Distance'] = distance_list.Similarity.apply(lambda x: vector_similarity(json.loads(x), embedding))
    distance_list = distance_list.sort_values('Distance', ascending=False)
    distance_list = distance_list.drop(columns='Similarity')
    distance_list.to_csv('./check.csv', index=False)
    context = ""

    for i in range(min(df.shape[0], context_instruction_limit)):
        instruction = distance_list.iloc[i]['Instruction']
        query = distance_list.iloc[i]['Query']
        context = f"{context}Human: {instruction}{terminator}AI: {query}{terminator}"

    context = f"{context}Human: {question}. {terminator}AI: "
    return context


# Send converstation context to OpenAI engine
def ask(question, chat_log=None):
    try:
        response = openai.Completion.create(
            prompt=generate_context(question),
            engine="text-davinci-003",
            temperature=0.3,
            max_tokens=200,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        story = response['choices'][0]['text']
        return str(story)

    except Exception as e:
        return str(e)


# Check if the received message from Slack is duplicated.
# Due to some system check, Slack sends user message to the bot multiple times
def is_duplicated_message(message):
    try:
        if os.stat('message.log').st_size != 0:
            with open('message.log', 'r') as f:
                old_message = json.load(f)
            if message in old_message:
                return True
            else:
                old_message.append(message)
                with open('message.log', 'w') as f:
                    json.dump(old_message, f)
                return False
        else:
            with open('message.log', 'w+') as f:
                json.dump([message], f)
            return False
    except FileNotFoundError:
        with open('message.log', 'w+') as f:
            json.dump([message], f)
        return False


# Get last message from message log store
def last_message():
    with open('message.log', 'r') as f:
        old_message = json.load(f)
    for message in reversed(old_message):
        if "amend" not in message.get('text').lower():
            return message.get('text')


# Bot endpoint to listen to user message
@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    user_id = event.get('user')
    text = event.get('text')
    if 'client_msg_id' in event:
        message_id = event.get('client_msg_id')
        message_log = {
            "client_msg_id": message_id,
            "text": text
        }
        if not is_duplicated_message(message_log):
            if "amend" in text.lower():
                text = last_message() + " " + text
            print(text)
            client.chat_postMessage(channel=user_id, text=ask(text))


# Ask endpoint to receive message from http://server-url/api API endpoint.
# It's serving Web UI function
@app.route("/ask", methods=['POST'])
def test():
    payload = request.json
    text = payload.get('text')
    message_log = {
        "client_msg_id": str(uuid.uuid1()),
        "text": text
    }
    is_duplicated_message(message_log)
    if "amend" in text.lower():
        text = last_message() + " " + text
    return jsonify(message=ask(text)), 200


# Serve index page
@app.route("/", methods=['GET'])
def web():
    return render_template('index.html')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
