import datetime, json, math, re
from tradingview import API as TradingViewAPI

QUOTE_REGEX = r'\$([A-Z\-\.]+)'

STARTUP_CASH = 100000.00

class Stocky:
    def __init__(self, client, redis):
        self.client = client
        self.redis = redis

    def getPriceEmoji(self, change):
        if change >= 0:
            return ':green_up:'
        else:
            return ':red_down:'


    def getPriceBlock(self, data):
        try:
            reco = data['technicals']['RECOMMENDATION']
            buy = data['technicals']['BUY']
            neutral = data['technicals']['NEUTRAL']
            sell = data['technicals']['SELL']
        except:
            reco = 'N/A'
            buy = 'N/A'
            neutral = 'N/A'
            sell = 'N/A'


        if 'current_session' not in data and data.keys() >= {'short_name', 'description', 'rtc', 'rch', 'rchp', 'rch'}:
            data['current_session'] = True
        elif 'current_session' not in data:
            print('Some weird issue:')
            print(data)
            return 'There was an error retrieving this symbol; try again later?'

        if data['current_session'] == 'pre_market':
            return '\n'.join([
                f'<https://finance.yahoo.com/quote/{data["short_name"]}|{data["description"]} ({data["short_name"]})>',
                f'>At Close: *{data["lp"]}* USD _{format(data["ch"], ".2f")} ({format(data["chp"], ".2f")}%)_ {self.getPriceEmoji(data["ch"])}',
                f'>Pre-Market: *{data["rtc"]}* USD _{format(data["rch"], ".2f")} ({format(data["rchp"], ".2f")}%)_ {self.getPriceEmoji(data["rch"])}',
                f'_1 Day Technical Analysis: *{reco.title()}* (Buy: {buy}, Neutral: {neutral}, Sell: {sell})_'
                ])
        elif data['current_session'] == 'post_market':
            return '\n'.join([
                f'<https://finance.yahoo.com/quote/{data["short_name"]}|{data["description"]}> ({data["short_name"]})>',
                f'>At Close: *{data["lp"]}* USD _{format(data["ch"], ".2f")} ({format(data["chp"], ".2f")}%)_ {self.getPriceEmoji(data["ch"])}',
                f'>Post-Market: *{data["rtc"]}* USD _{format(data["rch"], ".2f")} ({format(data["rchp"], ".2f")}%)_ {self.getPriceEmoji(data["rch"])}',
                f'_1 Day Technical Analysis: *{reco.title()}* (Buy: {buy}, Neutral: {neutral}, Sell: {sell})_'
            ])
        else:
            return '\n'.join([
                f'<https://finance.yahoo.com/quote/{data["short_name"]}|{data["description"]} ({data["short_name"]})>',
                f'>Last: *{data["lp"]}* USD _{format(data["ch"], ".2f") if "ch" in data else ""} ({format(data["chp"], ".2f") if "chp" in data else ""}%)_ {self.getPriceEmoji(data["ch"]) if "ch" in data else ""}',
                f'_1 Day Technical Analysis: *{reco.title()}* (Buy: {buy}, Neutral: {neutral}, Sell: {sell})_'
            ])

    def help(self, event):
        commands = [
            '  !funds                - See your available funds.',
            '  !portfolio            - See the stonks in your portfolio.',
            '  !buy [qty] [ticker]   - Buy [qty] shares of [ticker] stonk at market price.',
            '  !sell [qty] [ticker]  - Sell [qty] shares of [ticker] stonk at market price.',
            '  !short [qty] [ticker] - Short [qty] shares of [ticker] stonk at market price.',
            '  !cover [qty] [ticker] - Cover [qty] shares of [ticker] stonk at market price.',
            '  !liquidate            - Sell and cover all shares you own at the market price.',
            '  !bankruptcy           - File for bankruptcy and reset your funds and portfolio.'
        ]
        self.client.chat_postMessage(
            channel=event.get('channel'),
            text=f'For now I know stonks - so if you want to play stonks, you\'ve come to the right place.\n```' + '\n'.join(commands) + '```'
        )


    def funds(self, event):
        if not self.redis.exists(f'stonk_cash:{event.get("user")}'):
            self.redis.set(f'stonk_cash:{event.get("user")}', STARTUP_CASH)
            funds = STARTUP_CASH
        else:
            funds = float(self.redis.get(f'stonk_cash:{event.get("user")}').decode())

        self.client.chat_postMessage(
            channel=event.get('channel'),
            text=f'<@{event.get("user")}> has {"${:,.2f}".format(funds)} for investing.'
        )


    def portfolio(self, event):
        positions = self.redis.get(f'stonk_positions:{event.get("user")}')
        if positions is None:
            positions = []
        else:
            positions = json.loads(positions.decode())
            positions.sort(key=lambda p: p['symbol'])

        gains = 0.0
        total = 0.0
        results = ["%5s | %8s | %8s | %12s | %12s | %12s | %12s" % (
                'Type', 'Symbol', 'Qty', 'Price Paid', 'Last Price', 'Value', 'Gain'
        ),
        '-' * 87]

        for position in positions:
            try:
                api = TradingViewAPI(position['symbol'])
                quote = api.getQuote(tech=False)
                price = float(quote['lp'] if 'lp' in quote else quote['rtc'])
                api.close()
            except:
                # Was the symbol delisted? Or just temp glitch
                price = 0.0


            if position['short']:
                net = position['quantity'] * (position['price'] - price)
            else:
                net = position['quantity'] * (price - position['price'])

            value = position['quantity'] * position['price']

            results.append("%5s | %8s | %8s | %12s | %12s | %12s | %12s" % (
                'Short' if position['short'] else 'Long',
                position['symbol'],
                position['quantity'],
                f'{"${:,.2f}".format(position["price"])}',
                f'{"${:,.2f}".format(price)}',
                f'{"${:,.2f}".format(value)}',
                f'{"${:,.2f}".format(net)}',
            ))

            gains += net
            total += value

        results.append("%44s %12s | %12s | %12s" % (
            '', 'Totals:',
            f'{"${:,.2f}".format(total)}',
            f'{"${:,.2f}".format(gains)}'
        ))

        if len(results) > 2:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{event.get("user")}>\'s portfolio:\n' + '```' + '\n'.join(results) + '```'
            )
        else:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{event.get("user")}>, your portfolio is empty! Buy! Buy! Buy!'
            )

        return results


    def buy(self, event, quantity, symbol):
        response = self._create_position(event, symbol, quantity)

        if response and response['status'] == 'ok':
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{response["user"]}> bought {response["quantity"]} shares of {response["symbol"]} at {"${:,.2f}".format(response["price"])}.'
            )


    def sell(self, event, quantity, symbol):
        self._close_position(event, symbol, quantity)


    def short(self, event, quantity, symbol):
        response = self._create_position(event, symbol, quantity, short=True)

        if response['status'] == 'ok':
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{response["user"]}> shorted {response["quantity"]} shares of {response["symbol"]} at {"${:,.2f}".format(response["price"])}.'
            )


    def cover(self, event, quantity, symbol):
        self._close_position(event, symbol, quantity, short=True)


    def _create_position(self, event, symbol, quantity=0, price=None, short=False):
        try:
            quantity = int(quantity)
            symbol = symbol.upper()
            if not price:
                api = TradingViewAPI(symbol)
                price = float(api.getQuote(tech=False)['lp'])
                api.close()
            else:
                price = float(price)
        except:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text='Is that even a real stock symbol? Perhaps I am just having trouble finding it at the moment... but let\'s be real - it\'s probably your fault.'
            )
            return

        if quantity <= 0:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'How do you expect to do anything with {quantity} shares?'
            )
            return

        if not self.redis.exists(f'stonk_cash:{event.get("user")}'):
            self.redis.set(f'stonk_cash:{event.get("user")}', STARTUP_CASH)

        positions = self.redis.get(f'stonk_positions:{event.get("user")}')
        if positions is None:
            positions = []
        else:
            positions = json.loads(positions.decode())

        cost = price * quantity


        funds = float(self.redis.get(f'stonk_cash:{event.get("user")}').decode())
        if cost > funds:
            available = math.floor(funds / price)

            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{event.get("user")}> You don\'t have enough funds to complete this -- at most you could do {available} shares.'
            )
            return

        position = {
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'date': datetime.datetime.now().timestamp(),
            'short': short
        }
        positions.append(position)

        self.redis.set(f'stonk_cash:{event.get("user")}', float(self.redis.get(f'stonk_cash:{event.get("user")}').decode()) - cost)
        self.redis.set(f'stonk_positions:{event.get("user")}', json.dumps(positions))

        self.redis.get('cash:{event.get("user")}')

        return {
            'status': 'ok',
            'user': event.get("user"),
            **position
        }



    def _close_position(self, event, symbol, quantity, price=None, short=False):
        try:
            quantity = int(quantity)
            symbol = symbol.upper()
            if not price:
                api = TradingViewAPI(symbol)
                price = float(api.getQuote(tech=False)['lp'])
                api.close()
            else:
                price = float(price)
        except:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text='Is that even a real stock symbol? Perhaps I am just having trouble finding it at the moment... but let\'s be real - it\'s probably your fault.'
            )
            return

        if quantity <= 0:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'How do you expect to do anything with {quantity} shares?'
            )
            return

        positions = json.loads(self.redis.get(f'stonk_positions:{event.get("user")}').decode())
        check = []
        keep = []
        for position in positions:
            if symbol == position['symbol'] and short == position['short']:
                check.append(position)
            else:
                keep.append(position)

        if not check:
            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'{symbol} is not even in your portfolio!'
            )
            return

        check.sort(key=lambda p: p['date'])

        for position in check:
            q = min(quantity, position['quantity'])

            basis = position['price'] * q
            value = price * q

            if short:
                net = basis - value
                self.redis.set(f'stonk_cash:{event.get("user")}', float(self.redis.get(f'stonk_cash:{event.get("user")}').decode()) + basis + net)
            else:
                net = value - basis
                self.redis.set(f'stonk_cash:{event.get("user")}', float(self.redis.get(f'stonk_cash:{event.get("user")}').decode()) + value)

            quantity -= q
            position['quantity'] -= q

            if position['quantity'] > 0:
                keep.append(position)

            self.client.chat_postMessage(
                channel=event.get('channel'),
                text=f'<@{event.get("user")}> {"covered" if position["short"] else "sold"} {q} shares of {symbol} at {"${:,.2f}".format(price)} (net: {"${:,.2f}".format(net)})'
            )

        self.redis.set(f'stonk_positions:{event.get("user")}', json.dumps(keep))


    def liquidate(self, event):
        positions = self.redis.get(f'stonk_positions:{event.get("user")}')
        if positions is None:
            return
        else:
            positions = json.loads(positions.decode())


        for position in positions:
            self._close_position(event, position['symbol'], position['quantity'], price=None, short=position['short'])


    def bankruptcy(self, event):
        self.redis.delete(f'stonk_cash:{event.get("user")}')
        self.redis.delete(f'stonk_positions:{event.get("user")}')

        def getSuffix(num):
            if 4 <= num <= 20 or 24 <= num <= 30:
                return 'th'
            else:
                return ['st', 'nd', 'rd'][num % 10 - 1]

        dt = datetime.datetime.now()

        self.client.chat_postMessage(
            channel=event.get('channel'),
            text=f'<!channel> Notice is hereby given, that on the {f"{dt.day}{getSuffix(dt.day)} day of {dt:%B}, A. D. {dt.year}"}, <@{event.get("user")}> was duly adjudicated bankrupt. If they owed you anything, tough shit.'
        )


    def check_quotes(self, event):
        try:
            matches = re.findall(QUOTE_REGEX, event.get('text'))
        except:
            return

        if not matches:
            return

        for quote in matches:
            api = TradingViewAPI(quote)

            try:
                data = api.getQuote()
            except Exception as e:
                print('Unable to getquote!')
                print(e)
                continue

            block = {
                'type': 'section',
                'block_id': f'{api.quote_session}',
                'text': {
                    'type': 'mrkdwn',
                    'text': self.getPriceBlock(data),
                }
            }

            try:
                chart_data = api.getChart()
                img = api.generateChartImage('./assets', chart_data, data['ch'])
                block['accessory'] = {
                    'type': 'image',
                    'image_url': f'http://sublim.nl:10312/assets/{img}',
                    'alt_text': f'Spark chart for {data["short_name"]}'
                }
            except:
                pass

            api.close()

            self.client.chat_postMessage(
                channel=event.get('channel'),
                blocks=[ block ],
                unfurl_links=False,
                unfurl_media=False
            )
