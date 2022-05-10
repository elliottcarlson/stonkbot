#!/usr/bin/env python3
import os
import re
import json
import logging
import random
import requests
import time
import threading
from cachetools import TTLCache
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from redis import Redis
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from math import sin, cos, sqrt, atan2, radians

from parser import Parser
from stocky import Stocky

load_dotenv()

app = Flask(__name__)

dupecache = TTLCache(maxsize=128, ttl=480)

parser = Parser()
slack_events_adapter = SlackEventAdapter(os.environ.get('SLACK_EVENTS_TOKEN'), '/slack/events/', app)
slack_web_client = WebClient(token=os.environ.get('SLACK_TOKEN'))
redis = Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'), db=os.environ.get('REDIS_DB'))

@slack_events_adapter.on('message')
def message(payload):
    logger.info(payload)
    event = payload.get('event', {})

    # Prevent answering the same slack message?
    if event.get('client_msg_id') in dupecache:
        return
    dupecache[event.get('client_msg_id')] = True

    # Never reply to another bot!
    if event.get('bot_id', False):
        return

    # Check for commands
    parsed = parser.parse(event.get('text'))
    if parsed is not None:
        method = parsed[0]

        # See if the command exists in Stocky
        if hasattr(stocky, method) and callable(getattr(stocky, method)):
            func = getattr(stocky, method)
            try:
                func(event, *parsed[1:])
            except:
                slack_web_client.chat_postMessage(
                    channel=event.get('channel'),
                    text='Get your inputs right or you won\'t get anywhere in life.'
                )
            return


    # See if there are stock quotes to look up!
    stocky.check_quotes(event)


@app.route('/assets/<path:path>')
def send_charts(path):
    return send_from_directory('assets', path)


if __name__ == '__main__':
    stocky = Stocky(slack_web_client, redis)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    app.run('0.0.0.0', port='10312')
