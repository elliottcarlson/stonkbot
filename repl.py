import os, sys, time
from dotenv import load_dotenv
from redis import Redis
from pprint import pprint
from parser import Parser

from stocky import Stocky

load_dotenv()

parser = Parser()
redis = Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'), db=os.environ.get('REDIS_DB'))
stocky = Stocky(None, redis)


def add(isbn):
    return f'{isbn} was added'

def delete(isbn):
    return f'{isbn} was deleted'


command_list = [add, delete]
commands = {f.__name__: f for f in command_list}

user = 'test_user' if len(sys.argv) != 2 else sys.argv[1]

print(f'Welcome {user}!')
print('Available commands:')
print('  !funds                     - Current available funds')
print('  !portfolio                 - Current portfolio')
print('  !buy [quantity] [symbol]   - Buy quantity of symbol at market price')
print('  !sell [quantity] [symbol]  - Sell quantity of symbol at market price')
print('  !short [quantity] [symbol] - Short quantity of symbol at market price')
print('  !cover [quantity] [symbol] - Cover quantity of symbol at market price')
print('  !reset                     - Reset current user data')
print('  !lookup [symbol]           - Get quote data on symbol')
while True:
    command = input('> ')

    if command == 'exit':
        print('Goodbye!')
        break

    parsed = parser.parse(command)
    print(parsed)
    if parsed is not None:
        method = parsed[0]
        if hasattr(stocky, method) and callable(getattr(stocky, method)):
            func = getattr(stocky, method)
            pprint(func(user, *parsed[1:]))
            continue

    print('Unknown command.')
