from abc import ABC, abstractmethod
import argparse
import logging
import json


class Basic(ABC):
    @abstractmethod
    def __init__(self):
        self.period = None
        self.debug = None
        self.currencies = None
        self.logger = None

        self.parse_args()
        self.get_logger()

    @abstractmethod
    def parse_args(self):
        parser = argparse.ArgumentParser(description="Input data")
        parser.add_argument("--period", dest="N", required=True, type=int)
        parser.add_argument("--debug", dest="debug")
        args, args_currencies = parser.parse_known_args()

        currencies = {}

        # Parse currencies
        for i in range(0, len(args_currencies), 2):
            currency_name = args_currencies[i][2:]
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

        self.period = args.N
        self.debug = debug
        self.currencies = currencies

    @abstractmethod
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

        self.logger = logger

    @abstractmethod
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
