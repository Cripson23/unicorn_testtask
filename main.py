import asyncio
from aiohttp import web
import argparse
import logging
import json
import requests
import re
import copy

from basic import Basic


class App(Basic):
    def __init__(self):
        self.period, self.debug, self.currencies = self.parse_args()
        self.logger = self.get_logger()
        self.loop = asyncio.get_event_loop()
        self.web_app = web.Application()

    def parse_args(self):
        # Args
        parser = argparse.ArgumentParser(description="Input data")
        parser.add_argument("-period", dest="N", required=True, type=int)
        parser.add_argument("-debug", dest="debug")
        args, args_currencies = parser.parse_known_args()

        currencies = {}

        for i in range(0, len(args_currencies), 2):
            currency_name = args_currencies[i][1:]
            currencies[currency_name] = {
                'amount': float(args_currencies[i + 1])
            }

        if len(currencies.keys()) < 2:
            raise Exception("Currencies not transferred (min. 2)")

        debug_true = ['1', 'true', 'y']

        if args.debug is not None and str(args.debug).lower() in debug_true:
            debug = True
        else:
            debug = False

        return args.N, debug, currencies

    def get_logger(self):
        logger = logging.getLogger()

        formatter = logging.Formatter(
            '%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(lineno)d - %(message)s',
            datefmt="'%H:%M:%S',")

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(formatter)
        logger.addHandler(consoleHandler)

        if self.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        return logger

    async def start_app(self):
        self.logger.info("App started!")

        asyncio.create_task(self.get_currencies_rate())
        asyncio.create_task(self.start_server())
        asyncio.create_task(self.changes_monitor())

        await asyncio.Event().wait()

    async def get_currencies_rate(self):
        while True:
            try:
                r = requests.get('https://www.cbr-xml-daily.ru/daily_json.js')

                rates = r.json()['Valute']

                for currency in self.currencies.keys():
                    currency = currency.lower()
                    if currency == 'rub':
                        self.currencies[currency]['rate'] = 1.
                        continue
                    if currency.upper() in rates:
                        self.currencies[currency]['rate'] = round(float(rates[currency.upper()]['Value']), 4)
                    else:
                        self.logger.critical(f"Unknown currency name: {currency}")
                        raise Exception(f"Unknown currency name")

            except Exception as ex:
                self.logger.error("Error while getting exchange rates")
                raise Exception(ex)

            finally:
                self.logger.info("Update exchange rate")

            await asyncio.sleep(self.period * 60)

    async def changes_monitor(self):
        self.logger.info("Start changes monitor")
        currencies_last = copy.deepcopy(self.currencies)
        while True:
            currencies = copy.deepcopy(self.currencies)
            if currencies != currencies_last:
                self.logger.warning("Data changes noticed")

                amount_message = ""
                rate_message = ""
                sum_amount_rub = 0
                for idx, currency in enumerate(self.currencies.keys()):
                    amount_message += f"{currency}: {self.currencies[currency]['amount']}\n"
                    sum_amount_rub += self.currencies[currency]['amount'] * self.currencies[currency]['rate']
                    for ids, curr in enumerate(self.currencies.keys()):
                        if ids > idx:
                            rate_message += f"{currency}-{curr}: {round(self.currencies[curr]['rate'] / self.currencies[currency]['rate'], 4)}\n"

                sum_message = "sum: "
                for currency in self.currencies.keys():
                    sum_message += f"{round(sum_amount_rub / self.currencies[currency]['rate'], 2)} {currency} / "
                sum_message = sum_message[:-2]

                self.logger.info(f"\n{amount_message}\n{rate_message}\n{sum_message}")

                currencies_last = currencies

            await asyncio.sleep(60)

    async def setup_routes(self):
        for currency in self.currencies.keys():
            self.web_app.router.add_get(f"/{currency}/get", self.get_currency)
        self.web_app.router.add_get(f"/amount/get", self.get_amount)
        self.web_app.router.add_post(f"/amount/set", self.set_amount)
        self.web_app.router.add_post(f"/modify", self.modify_amount)

    async def req_res_debug(self, request, res):
        content = await request.read()
        request_info = {
            'method': str(request.method),
            'url': str(request.url),
            'host': str(request.host),
            'headers': str(request.headers),
            'content-type': str(request.content_type),
            'content': str(content)
        }

        response_info = {
            'status': str(res.status),
            'headers': str(res.headers),
            'content-type': str(res.content_type),
            'content': str(res.text)
        }

        self.logger.debug("Request info: " + json.dumps(request_info))
        self.logger.debug("Response info: " + json.dumps(response_info))

    async def get_currency(self, request):
        get_currency = str(re.findall(r'\/(...)\/', str(request.url))[0])
        response_body = {get_currency: copy.deepcopy(self.currencies[get_currency])}
        for currency in self.currencies.keys():
            if currency != get_currency:
                response_body[get_currency][currency] = round(float(response_body[get_currency]['amount']) * float(response_body[get_currency]['rate']) / float(self.currencies[currency]['rate']), 4)

        res = web.json_response(response_body, content_type="text/plain")

        if self.debug is True:
            await self.req_res_debug(request, res)

        return res

    async def get_amount(self, request):
        response_body = {'amount': {}, 'rate': {}, 'sum': {}}
        sum_amount_rub = 0
        for idx, currency in enumerate(self.currencies.keys()):
            response_body['amount'][currency] = copy.deepcopy(self.currencies[currency]['amount'])
            sum_amount_rub += self.currencies[currency]['amount'] * self.currencies[currency]['rate']
            for ids, curr in enumerate(self.currencies.keys()):
                if ids > idx:
                    response_body['rate'][f'{currency}-{curr}'] = round(self.currencies[curr]['rate'] / self.currencies[currency]['rate'], 4)

        for currency in self.currencies.keys():
            response_body['sum'][currency] = round(sum_amount_rub / self.currencies[currency]['rate'], 2)

        res = web.json_response(response_body, content_type="text/plain")
        if self.debug is True:
            await self.req_res_debug(request, res)

        return res

    async def set_amount(self, request):
        if request.body_exists:
            res = await request.read()
            data = json.loads(res)
            for currency in data.keys():
                if currency not in self.currencies:
                    self.logger.error(f"Unknown currency name: {currency}")
                    return web.json_response(f"Unknown currency name: {currency}", content_type="text/plain")

                data[currency] = float(data[currency])
                if data[currency] < 0:
                    self.logger.error(f"Negative amount")
                    return web.json_response(f"Amount must not be negative", content_type="text/plain")

                self.currencies[currency]['amount'] = data[currency]
            return web.json_response("Amount set successfully", content_type="text/plain")
        else:
            return web.json_response("Invalid data passed", content_type="text/plain")

    async def modify_amount(self, request):
        if request.body_exists:
            data = await request.read()
            data = json.loads(data)
            for currency in data.keys():
                if currency not in self.currencies:
                    self.logger.error(f"Unknown currency name: {currency}")
                    res = web.json_response(f"Unknown currency name: {currency}")
                    if self.debug is True:
                        await self.req_res_debug(request, res)
                    return res
                self.currencies[currency]['amount'] += float(data[currency])
                if self.currencies[currency]['amount'] < 0:
                    self.currencies[currency]['amount'] = 0
            res = web.json_response("Amount modify successfully", content_type="text/plain")
            if self.debug is True:
                await self.req_res_debug(request, res)
            return res
        else:
            res = web.json_response("Invalid data passed", content_type="text/plain")
            if self.debug is True:
                await self.req_res_debug(request, res)
            return res

    async def start_server(self):
        await self.setup_routes()
        runner = web.AppRunner(self.web_app)
        await runner.setup()
        site = web.TCPSite(runner)
        await site.start()
        self.logger.info("The server has been started")


if __name__ == '__main__':
    asyncio.run(App().start_app())
