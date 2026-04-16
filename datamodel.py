from typing import Dict, List

class Order:
    def __init__(self, symbol: str, price: int, quantity: int):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

class Listing:
    def __init__(self, symbol: str, product: str, denomination: str):
        self.symbol = symbol
        self.product = product
        self.denomination = denomination

class Trade:
    def __init__(self, symbol: str, price: int, quantity: int, buyer: str = "", seller: str = "", timestamp: int = 0):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.buyer = buyer
        self.seller = seller
        self.timestamp = timestamp

class OrderDepth:
    def __init__(self):
        self.buy_orders: Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}

class Observations:
    def __init__(self, plainValueObservations: Dict[str, float] = {}):
        self.plainValueObservations = plainValueObservations

class TradingState:
    def __init__(self, timestamp: int, listings: Dict[str, Listing], order_depths: Dict[str, OrderDepth], own_trades: Dict[str, List[Trade]], market_trades: Dict[str, List[Trade]], position: Dict[str, int], observations: Observations):
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations