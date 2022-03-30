import asyncio
import json
import requests
import re
import copy
from aiohttp import web

from basic import Basic


class App(Basic):
    def __init__(self):
        super().__init__()

    def parse_args(self):
        super().parse_args()

    def get_logger(self):
        super().get_logger()

    async def req_res_debug(self, request, res):
        await super().req_res_debug(request, res)

    async def start_app(self):
        self.logger.info("App started!")

        asyncio.get_event_loop()
        asyncio.create_task(self.get_currencies_rate())
        asyncio.create_task(self.changes_monitor())
        asyncio.create_task(self.start_server())

        await asyncio.Event().wait()

    # Обновление курсов
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

    # Отслеживание изменений в данных
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
                    # Считаем общую сумму в рублях
                    sum_amount_rub += self.currencies[currency]['amount'] * self.currencies[currency]['rate']
                    # Проходимся по каждой валюте, идущей после текущей и находим курс
                    for ids, curr in enumerate(self.currencies.keys()):
                        if ids > idx:
                            rate_message += f"{currency}-{curr}: {round(self.currencies[curr]['rate'] / self.currencies[currency]['rate'], 4)}\n"

                sum_message = "sum: "
                # Переводим сумму в каждую из валют и добавляем в сообщение
                for currency in self.currencies.keys():
                    sum_message += f"{round(sum_amount_rub / self.currencies[currency]['rate'], 2)} {currency} / "
                sum_message = sum_message[:-2]

                self.logger.info(f"\n{amount_message}\n{rate_message}\n{sum_message}")

                currencies_last = currencies

            await asyncio.sleep(60)

    # Server
    async def start_server(self):
        web_app = web.Application()
        await self.setup_routes(web_app)
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner)
        await site.start()
        self.logger.info("The server has been started")

    # Роуты
    async def setup_routes(self, web_app):
        for currency in self.currencies.keys():
            web_app.router.add_get(f"/{currency}/get", self.get_currency)
        web_app.router.add_get(f"/amount/get", self.get_amount)
        web_app.router.add_post(f"/amount/set", self.set_amount)
        web_app.router.add_post(f"/modify", self.modify_amount)

    # /{currency}/get
    async def get_currency(self, request):
        get_currency = str(re.findall(r'\/(...)\/', str(request.url))[0])  # получаем наим. текущей валюты
        response_body = {get_currency: copy.deepcopy(self.currencies[get_currency])}
        for currency in self.currencies.keys():  # проходимся по всем валютам кроме текущей
            if currency != get_currency:
                # Узнаем суммы в других валютах
                # кол-во валюты умножаем на курс в рублях и переводим во вторую валюту путём деления на её курс
                response_body[get_currency][currency] = round(
                    float(response_body[get_currency]['amount']) * float(response_body[get_currency]['rate']) / float(
                        self.currencies[currency]['rate']), 4)

        res = web.json_response(response_body, content_type="text/plain")

        if self.debug is True:
            await self.req_res_debug(request, res)

        return res

    # /amount/get
    async def get_amount(self, request):
        response_body = {'amount': {}, 'rate': {}, 'sum': {}}
        sum_amount_rub = 0
        for idx, currency in enumerate(self.currencies.keys()):
            response_body['amount'][currency] = copy.deepcopy(self.currencies[currency]['amount'])
            # Считаем общую сумму в рублях
            sum_amount_rub += self.currencies[currency]['amount'] * self.currencies[currency]['rate']
            # Проходимся по каждой валюте, идущей после текущей и находим курс
            for ids, curr in enumerate(self.currencies.keys()):
                if ids > idx:
                    response_body['rate'][f'{currency}-{curr}'] = round(self.currencies[curr]['rate'] / self.currencies[currency]['rate'], 4)

        # Переводим сумму в каждую из валют
        for currency in self.currencies.keys():
            response_body['sum'][currency] = round(sum_amount_rub / self.currencies[currency]['rate'], 2)

        res = web.json_response(response_body, content_type="text/plain")
        if self.debug is True:
            await self.req_res_debug(request, res)

        return res

    # /amount/set
    async def set_amount(self, request):
        if request.body_exists:
            res = await request.read()
            data = json.loads(res)
            for currency in data.keys():
                if currency not in self.currencies:
                    self.logger.error(f"Unknown currency name: {currency}")
                    res = web.json_response(f"Unknown currency name: {currency}", content_type="text/plain")
                    if self.debug is True:
                        await self.req_res_debug(request, res)
                    return res

                data[currency] = float(data[currency])
                if data[currency] < 0:
                    self.logger.error(f"Negative amount")
                    res = web.json_response(f"Amount must not be negative", content_type="text/plain")
                    if self.debug is True:
                        await self.req_res_debug(request, res)
                    return res

                self.currencies[currency]['amount'] = data[currency]
            res = web.json_response("Amount set successfully", content_type="text/plain")
            if self.debug is True:
                await self.req_res_debug(request, res)
            return res
        else:
            res = web.json_response("Invalid data passed", content_type="text/plain")
            if self.debug is True:
                await self.req_res_debug(request, res)
            return res

    # /modify
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


if __name__ == '__main__':
    asyncio.run(App().start_app())
