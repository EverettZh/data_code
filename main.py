from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import math

LIMIT = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

class Trader:
    def __init__(self):
        self.pepper_anchor = None
        self.pepper_first_ts = None

    def best_bid_ask(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None, None
        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())
        return best_bid, best_ask

    def mid(self, depth: OrderDepth):
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return None
        return (best_bid + best_ask) / 2

    def buy_capacity(self, product: str, pos: int) -> int:
        return max(0, LIMIT[product] - pos)

    def sell_capacity(self, product: str, pos: int) -> int:
        return max(0, LIMIT[product] + pos)

    def trade_pepper(self, product: str, depth: OrderDepth, pos: int, timestamp: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return orders

        mid = (best_bid + best_ask) / 2

        # infer day anchor from first seen observation
        if self.pepper_anchor is None:
            self.pepper_first_ts = timestamp
            self.pepper_anchor = round(mid - timestamp / 1000)

        fair = self.pepper_anchor + timestamp / 1000

        # inventory skew
        skew = pos * 0.05
        fair_adj = fair - skew

        # take obviously good prices
        if best_ask <= fair_adj - 1:
            qty = min(self.buy_capacity(product, pos), -depth.sell_orders[best_ask], 20)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                pos += qty

        if best_bid >= fair_adj + 1:
            qty = min(self.sell_capacity(product, pos), depth.buy_orders[best_bid], 20)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                pos -= qty

        # passive quotes
        bid_px = math.floor(fair_adj - 1)
        ask_px = math.ceil(fair_adj + 1)

        buy_qty = min(self.buy_capacity(product, pos), 12)
        sell_qty = min(self.sell_capacity(product, pos), 12)

        if buy_qty > 0 and pos < 65:
            orders.append(Order(product, bid_px, buy_qty))
        if sell_qty > 0 and pos > -65:
            orders.append(Order(product, ask_px, -sell_qty))

        return orders

    def trade_osmium(self, product: str, depth: OrderDepth, pos: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return orders

        fair = 10000
        skew = pos * 0.08
        fair_adj = fair - skew

        # aggressive mean reversion
        if best_ask <= fair_adj - 2:
            qty = min(self.buy_capacity(product, pos), -depth.sell_orders[best_ask], 20)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                pos += qty

        if best_bid >= fair_adj + 2:
            qty = min(self.sell_capacity(product, pos), depth.buy_orders[best_bid], 20)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                pos -= qty

        # passive market making
        bid_px = math.floor(fair_adj - 1)
        ask_px = math.ceil(fair_adj + 1)

        buy_qty = min(self.buy_capacity(product, pos), 10)
        sell_qty = min(self.sell_capacity(product, pos), 10)

        if buy_qty > 0 and pos < 65:
            orders.append(Order(product, bid_px, buy_qty))
        if sell_qty > 0 and pos > -65:
            orders.append(Order(product, ask_px, -sell_qty))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product, depth in state.order_depths.items():
            pos = state.position.get(product, 0)

            if product == "INTARIAN_PEPPER_ROOT":
                result[product] = self.trade_pepper(product, depth, pos, state.timestamp)
            elif product == "ASH_COATED_OSMIUM":
                result[product] = self.trade_osmium(product, depth, pos)
            else:
                result[product] = []

        return result, 0, ""