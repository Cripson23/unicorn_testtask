from abc import ABC, abstractmethod


class Basic(ABC):
    @staticmethod
    def parse_args():
        pass

    @abstractmethod
    def get_logger(self):
        pass

    @abstractmethod
    def start_app(self):
        pass

    @abstractmethod
    def get_currencies_rate(self):
        pass

    @abstractmethod
    def changes_monitor(self):
        pass

    @abstractmethod
    def setup_routes(self):
        pass

    @abstractmethod
    def req_res_debug(self, request, res):
        pass

    @abstractmethod
    def get_currency(self, request):
        pass

    @abstractmethod
    def get_amount(self, request):
        pass

    @abstractmethod
    def set_amount(self, request):
        pass

    @abstractmethod
    def modify_amount(self, request):
        pass

    @abstractmethod
    def start_server(self):
        pass
