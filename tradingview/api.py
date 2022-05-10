import json, os, pytz, random, re, string
from websocket import create_connection
from datetime import datetime, time, timedelta
from PIL import Image
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from tradingview_ta import TA_Handler, Interval


EST = pytz.timezone('US/Eastern')


def filter_date(date):
    timestamp = datetime.fromtimestamp(date)
    local = EST.localize(timestamp)

    if time() < time(9,30):
        yesterday = datetime.today().date() - timedelta(days=1)
        if local.date() == yesterday:
            return True

    if local.date() < datetime.today().date():
        return False

    return True


class API:
    def __init__(self, symbol):
        headers = json.dumps({
            'Origin': 'https://data.tradingview.com'
        })
        self.ws = create_connection('wss://data.tradingview.com/socket.io/websocket', headers=headers)
        self.symbol = symbol
        self.quote_session = self.generateSession('qs_')
        self.chart_session = self.generateSession('cs_')


    def generateSession(self, prefix):
        stringLength = 12
        letters = string.ascii_lowercase
        random_string = ''.join(random.choice(letters) for i in range(stringLength))
        return prefix + random_string


    def prependHeader(self, m):
        return '~m~' + str(len(m)) + '~m~' + m


    def constructMessage(self, func, params):
        return json.dumps({
            'm': func,
            'p': params,
        }, separators=(',', ':'))


    def createMessage(self, func, params):
        return self.prependHeader(self.constructMessage(func, params))


    def sendMessage(self, func, args):
        self.ws.send(self.createMessage(func, args))


    def close(self):
        self.ws.close()


    def parseMessage(self, m):
        lines = re.split(r'~m~[0-9]+~m~', m)
        for i in range(len(lines)):
            try:
                lines[i] = json.loads(lines[i])
            except Exception as e:
                lines[i] = {}

        return lines


    def getQuote(self, tech=True):
        self.sendMessage('set_data_quality', ['low'])
        self.sendMessage('set_auth_token', ['unauthorized_user_token'])
        self.sendMessage('quote_create_session', [self.quote_session])
        self.sendMessage('quote_add_symbols', [self.quote_session, self.symbol, {'flags': ['force_permission']}])

        receiving = True
        cnt = 0
        data = {}
        while receiving:
            result = self.parseMessage(self.ws.recv())
            for resp in result:
                if 'm' not in resp:
                    continue

                if resp['m'] == 'quote_completed':
                    receiving = False
                    break

                if resp['p'][1]['s'] == 'error':
                    raise Exception()

                data.update(resp['p'][1]['v'])

                cnt = cnt + 1
                if cnt > 3:
                    receiving = False
                    break

        if tech:
            try:
                technicals = TA_Handler(
                    symbol=self.symbol,
                    screener='america',
                    exchange=data['listed_exchange'],
                    interval=Interval.INTERVAL_1_DAY
                )

                data['technicals'] = technicals.get_analysis().summary
            except:
                pass

        return data


    def getChart(self):
        self.sendMessage('chart_create_session', [self.chart_session])
        self.sendMessage('switch_timezone', [self.chart_session, 'Etc/UTC'])
        self.sendMessage('resolve_symbol', [self.chart_session, 'symbol_1', f'={{"symbol":"{self.symbol}","adjustment":"splits","session":"extended"}}'])
        self.sendMessage('create_series', [self.chart_session, 's1', 's1', 'symbol_1', '3', 300])

        receiving = True
        chart_data = []
        while receiving:
            result = self.parseMessage(self.ws.recv())

            for resp in result:
                if 'm' not in resp or resp['m'] in ['series_loading', 'symbol_resolved']:
                    continue

                if resp['m'] == 'series_completed':
                    receiving = False
                    break

                try:
                    chart_data = resp['p'][1]['s1']['s']
                except:
                    pass

        points = [ i['v'][4] for i in chart_data if filter_date(i['v'][0]) ]

        return points


    def generateChartImage(self, path, data, chg, figsize=(10, 10), **kwargs):
        save_to = os.path.join(path, f'{self.chart_session}.png')

        fig,ax = plt.subplots(1, 1, figsize=figsize, **kwargs)

        if chg >= 0:
            ax.plot(data, 'g-')
            color = 'green'
        else:
            ax.plot(data, 'r-')
            color = 'red'

        for k, v in ax.spines.items():
            v.set_visible(False)

        ax.set_xticks([])
        ax.set_yticks([])

        plt.plot(len(data)-1, data[len(data)-1], 'r.')

        ax.fill_between(range(len(data)), data, len(data) * [min(data)], alpha=0.1, color=color)

        plt.savefig(save_to, bbox_inches='tight')

#        im = Image.open(save_to)
#        newim = im.resize((250, 250))
#        newim.save(save_to, 'PNG')

        return f'{self.chart_session}.png'
