from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import math
import statistics
# import pandas as pd  # Commented out for submission

LIMIT = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

class Trader:
    def __init__(self):
        # Price history for regression models
        self.price_history = {"ASH_COATED_OSMIUM": [], "INTARIAN_PEPPER_ROOT": []}
        self.timestamp_history = []
        self.max_history = 20  # Keep last 20 observations

        # Pairs trading parameters
        self.spread_history = []
        self.spread_mean = None
        self.spread_std = None

        # Dynamic parameters
        self.volatility = {"ASH_COATED_OSMIUM": 1.0, "INTARIAN_PEPPER_ROOT": 1.0}

        # Simple strategy comparison tracking
        self.strategy_name = "passive_maker"
        self.strategy_metrics = {
            self.strategy_name: {
                "timestamps": [],
                "order_count": 0,
                "volume": 0,
                "max_position": 0,
            }
        }
        self.strategy_history = []

    def update_history(self, product: str, price: float, timestamp: int):
        """Update price history for statistical models"""
        self.price_history[product].append(price)
        if len(self.price_history[product]) > self.max_history:
            self.price_history[product].pop(0)

        if timestamp not in self.timestamp_history:
            self.timestamp_history.append(timestamp)
            if len(self.timestamp_history) > self.max_history:
                self.timestamp_history.pop(0)

    def predict_price_osmium(self) -> float:
        """Predict next osmium price using linear regression on recent prices"""
        prices = self.price_history["ASH_COATED_OSMIUM"]
        if len(prices) < 4:
            return prices[-1] if prices else 10000  # fallback to last known price

        # Simple linear regression: price = a + b * time_index
        x = list(range(len(prices)))
        y = prices

        # Calculate slope and intercept manually
        if len(x) > 1:
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)

            denominator = n * sum_x2 - sum_x * sum_x
            if denominator != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denominator
                intercept = (sum_y - slope * sum_x) / n
                predicted = intercept + slope * len(prices)
            else:
                predicted = prices[-1]
        else:
            predicted = prices[-1]

        return max(9000, min(11000, predicted))  # Clamp to reasonable range

    def predict_price_pepper(self, timestamp: int) -> float:
        """Predict pepper price using time-based model with trend"""
        prices = self.price_history["INTARIAN_PEPPER_ROOT"]
        if len(prices) < 2:
            return prices[-1] if prices else 10000  # fallback to last known price

        # Use exponential moving average with trend
        if len(prices) >= 2:
            ema = self.calculate_ema(prices, 0.2)
            # Add small trend component based on recent movement
            trend = (prices[-1] - prices[-2]) * 0.1
            predicted = ema + trend
        else:
            predicted = prices[-1]

        return max(9500, min(10500, predicted))  # Pepper is more stable

    def calculate_ema(self, prices: List[float], alpha: float) -> float:
        """Calculate exponential moving average"""
        ema = prices[0]
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def update_spread_stats(self):
        """Update spread statistics for pairs trading"""
        if len(self.price_history["ASH_COATED_OSMIUM"]) >= 2 and len(self.price_history["INTARIAN_PEPPER_ROOT"]) >= 2:
            # Calculate spread: osmium - 1.0 * pepper (assume 1:1 relationship)
            spread = self.price_history["ASH_COATED_OSMIUM"][-1] - self.price_history["INTARIAN_PEPPER_ROOT"][-1]
            self.spread_history.append(spread)

            if len(self.spread_history) > self.max_history:
                self.spread_history.pop(0)

            if len(self.spread_history) >= 5:
                self.spread_mean = statistics.mean(self.spread_history)
                self.spread_std = statistics.stdev(self.spread_history) if len(self.spread_history) > 1 else 1.0

    def calculate_volatility(self, product: str) -> float:
        """Calculate realized volatility"""
        prices = self.price_history[product]
        if len(prices) < 3:
            return 1.0

        returns = [math.log(prices[i]/prices[i-1]) for i in range(1, len(prices))]
        if returns:
            vol = statistics.stdev(returns) * math.sqrt(len(returns)) if len(returns) > 1 else abs(returns[0])
            self.volatility[product] = max(0.1, min(5.0, vol))  # Clamp volatility
        return self.volatility[product]

    def best_bid_ask(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None, None
        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())
        return best_bid, best_ask

    def weighted_mid_price(self, depth: OrderDepth, levels: int = 3) -> float:
        """Calculate weighted mid-price using multiple order book levels"""
        if not depth.buy_orders or not depth.sell_orders:
            return None

        # Get top levels
        bids = sorted(depth.buy_orders.keys(), reverse=True)[:levels]
        asks = sorted(depth.sell_orders.keys())[:levels]

        total_bid_volume = sum(depth.buy_orders.get(bid, 0) for bid in bids)
        total_ask_volume = sum(depth.sell_orders.get(ask, 0) for ask in asks)

        if total_bid_volume == 0 or total_ask_volume == 0:
            return None

        weighted_bid = sum(bid * depth.buy_orders.get(bid, 0) for bid in bids) / total_bid_volume
        weighted_ask = sum(ask * depth.sell_orders.get(ask, 0) for ask in asks) / total_ask_volume

        return (weighted_bid + weighted_ask) / 2

    def order_book_imbalance(self, depth: OrderDepth) -> float:
        """Calculate order book imbalance (-1 to 1, positive means buy pressure)"""
        total_buy_volume = sum(depth.buy_orders.values())
        total_sell_volume = sum(depth.sell_orders.values())

        if total_buy_volume + total_sell_volume == 0:
            return 0

        return (total_buy_volume - total_sell_volume) / (total_buy_volume + total_sell_volume)

    def buy_capacity(self, product: str, pos: int) -> int:
        return max(0, LIMIT[product] - pos)

    def sell_capacity(self, product: str, pos: int) -> int:
        return max(0, LIMIT[product] + pos)

    def dynamic_skew(self, product: str, pos: int) -> float:
        """Dynamic inventory skew based on position and volatility"""
        base_skew = 0.05
        vol_adjustment = self.volatility[product] * 0.02
        pos_factor = abs(pos) / LIMIT[product]
        return base_skew + vol_adjustment + pos_factor * 0.1

    def log_strategy_activity(self, timestamp: int, product: str, orders: List[Order], pos: int):
        metrics = self.strategy_metrics.setdefault(self.strategy_name, {
            "timestamps": [],
            "order_count": 0,
            "volume": 0,
            "max_position": 0,
        })
        metrics["timestamps"].append(timestamp)
        metrics["order_count"] += len(orders)
        metrics["volume"] += sum(abs(order.quantity) for order in orders)
        metrics["max_position"] = max(metrics["max_position"], abs(pos))
        self.strategy_history.append({
            "timestamp": timestamp,
            "strategy": self.strategy_name,
            "product": product,
            "orders": [(order.price, order.quantity) for order in orders],
            "position": pos,
        })

    def trade_simple(self, product: str, depth: OrderDepth, pos: int, timestamp: int, max_quote: int = 1) -> List[Order]:
        """Simple market maker with inventory management."""
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return orders

        # Base prices inside the spread
        buy_px = best_bid + 1
        sell_px = best_ask - 1

        # Inventory adjustment: scale skew with position ratio
        pos_ratio = abs(pos) / LIMIT[product]
        if pos > 0:
            sell_px -= min(1, int(pos_ratio * 2))  # Better sell to reduce long
        elif pos < 0:
            buy_px += min(1, int(pos_ratio * 2))  # Better buy to reduce short

        # Quote size: 4 when neutral, 1 when biased
        quote_size = 1 if abs(pos) > 20 else 4

        # Quote respecting limits
        if self.buy_capacity(product, pos) > 0:
            orders.append(Order(product, buy_px, quote_size))
        if self.sell_capacity(product, pos) > 0:
            orders.append(Order(product, sell_px, -quote_size))

        return orders

    def trade_pepper(self, product: str, depth: OrderDepth, pos: int, timestamp: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return orders

        # Update price history
        mid_price = (best_bid + best_ask) / 2
        self.update_history(product, mid_price, timestamp)

        # Predict fair price
        fair = self.predict_price_pepper(timestamp)

        # Update volatility
        self.calculate_volatility(product)

        # Dynamic parameters
        skew = self.dynamic_skew(product, pos)
        fair_adj = fair - skew * pos

        # Order book analysis
        imbalance = self.order_book_imbalance(depth)
        spread = best_ask - best_bid

        # Adjust for market pressure
        if imbalance > 0.3:  # Buy pressure
            fair_adj += 0.5
        elif imbalance < -0.3:  # Sell pressure
            fair_adj -= 0.5

        # Aggressive trading with dynamic thresholds
        vol_multiplier = max(0.5, min(2.0, 1 / self.volatility[product]))
        aggressive_threshold = 1.0 * vol_multiplier

        if best_ask <= fair_adj - aggressive_threshold:
            qty = min(self.buy_capacity(product, pos), -depth.sell_orders[best_ask], int(15 * vol_multiplier))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid >= fair_adj + aggressive_threshold:
            qty = min(self.sell_capacity(product, pos), depth.buy_orders[best_bid], int(15 * vol_multiplier))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        # Passive market making with order book undercutting
        bid_px = math.floor(fair_adj - 0.5)
        ask_px = math.ceil(fair_adj + 0.5)

        # Undercut existing orders slightly
        if depth.buy_orders:
            best_bid_in_book = max(depth.buy_orders.keys())
            bid_px = min(bid_px, best_bid_in_book + 1)

        if depth.sell_orders:
            best_ask_in_book = min(depth.sell_orders.keys())
            ask_px = max(ask_px, best_ask_in_book - 1)

        # Dynamic order sizing based on position and volatility
        max_order_size = int(12 / self.volatility[product])
        buy_qty = min(self.buy_capacity(product, pos), max_order_size)
        sell_qty = min(self.sell_capacity(product, pos), max_order_size)

        # Position-based quoting restrictions
        pos_limit_pct = 0.8  # Don't quote if position > 80% of limit
        if buy_qty > 0 and pos < LIMIT[product] * pos_limit_pct:
            orders.append(Order(product, bid_px, buy_qty))
        if sell_qty > 0 and pos > -LIMIT[product] * pos_limit_pct:
            orders.append(Order(product, ask_px, -sell_qty))

        return orders

    def trade_osmium(self, product: str, depth: OrderDepth, pos: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None:
            return orders

        # Update price history
        mid_price = (best_bid + best_ask) / 2
        self.update_history(product, mid_price, 0)  # No timestamp for osmium

        # Predict fair price using regression
        fair = self.predict_price_osmium()

        # Update volatility
        self.calculate_volatility(product)

        # Dynamic parameters
        skew = self.dynamic_skew(product, pos) * 1.5  # Higher skew for volatile asset
        fair_adj = fair - skew * pos

        # Order book analysis
        imbalance = self.order_book_imbalance(depth)

        # Adjust for market pressure (more sensitive for volatile asset)
        if imbalance > 0.2:
            fair_adj += 1.0
        elif imbalance < -0.2:
            fair_adj -= 1.0

        # Aggressive trading with wider thresholds for volatile asset
        vol_multiplier = max(0.3, min(3.0, 1 / self.volatility[product]))
        aggressive_threshold = 2.0 * vol_multiplier

        if best_ask <= fair_adj - aggressive_threshold:
            qty = min(self.buy_capacity(product, pos), -depth.sell_orders[best_ask], int(20 * vol_multiplier))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid >= fair_adj + aggressive_threshold:
            qty = min(self.sell_capacity(product, pos), depth.buy_orders[best_bid], int(20 * vol_multiplier))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        # Passive market making
        bid_px = math.floor(fair_adj - 1)
        ask_px = math.ceil(fair_adj + 1)

        # Undercut existing orders
        if depth.buy_orders:
            best_bid_in_book = max(depth.buy_orders.keys())
            bid_px = min(bid_px, best_bid_in_book + 1)

        if depth.sell_orders:
            best_ask_in_book = min(depth.sell_orders.keys())
            ask_px = max(ask_px, best_ask_in_book - 1)

        # Dynamic order sizing
        max_order_size = int(10 / self.volatility[product])
        buy_qty = min(self.buy_capacity(product, pos), max_order_size)
        sell_qty = min(self.sell_capacity(product, pos), max_order_size)

        pos_limit_pct = 0.75  # More conservative for volatile asset
        if buy_qty > 0 and pos < LIMIT[product] * pos_limit_pct:
            orders.append(Order(product, bid_px, buy_qty))
        if sell_qty > 0 and pos > -LIMIT[product] * pos_limit_pct:
            orders.append(Order(product, ask_px, -sell_qty))

        return orders

    def pairs_trading(self, state: TradingState) -> Dict[str, List[Order]]:
        """Execute pairs trading between pepper and osmium"""
        orders = {"ASH_COATED_OSMIUM": [], "INTARIAN_PEPPER_ROOT": []}

        if self.spread_mean is None or self.spread_std is None:
            return orders

        # Current spread
        pepper_depth = state.order_depths.get("INTARIAN_PEPPER_ROOT")
        osmium_depth = state.order_depths.get("ASH_COATED_OSMIUM")

        if not pepper_depth or not osmium_depth:
            return orders

        pepper_mid = self.weighted_mid_price(pepper_depth)
        osmium_mid = self.weighted_mid_price(osmium_depth)

        if pepper_mid is None or osmium_mid is None:
            return orders

        osmium_px = int(round(osmium_mid))
        pepper_px = int(round(pepper_mid))

        current_spread = osmium_mid - pepper_mid
        z_score = (current_spread - self.spread_mean) / self.spread_std if self.spread_std > 0 else 0

        pos_pepper = state.position.get("INTARIAN_PEPPER_ROOT", 0)
        pos_osmium = state.position.get("ASH_COATED_OSMIUM", 0)

        # Pairs trading thresholds
        entry_threshold = 1.5
        exit_threshold = 0.5

        if z_score > entry_threshold:
            # Spread too high: short osmium, long pepper
            if pos_osmium > -self.sell_capacity("ASH_COATED_OSMIUM", pos_osmium) + 10:
                orders["ASH_COATED_OSMIUM"].append(Order("ASH_COATED_OSMIUM", osmium_px, -10))
            if pos_pepper < self.buy_capacity("INTARIAN_PEPPER_ROOT", pos_pepper) - 10:
                orders["INTARIAN_PEPPER_ROOT"].append(Order("INTARIAN_PEPPER_ROOT", pepper_px, 10))

        elif z_score < -entry_threshold:
            # Spread too low: long osmium, short pepper
            if pos_osmium < self.buy_capacity("ASH_COATED_OSMIUM", pos_osmium) - 10:
                orders["ASH_COATED_OSMIUM"].append(Order("ASH_COATED_OSMIUM", osmium_px, 10))
            if pos_pepper > -self.sell_capacity("INTARIAN_PEPPER_ROOT", pos_pepper) + 10:
                orders["INTARIAN_PEPPER_ROOT"].append(Order("INTARIAN_PEPPER_ROOT", pepper_px, -10))

        elif abs(z_score) < exit_threshold:
            # Close positions if spread normalizes
            if pos_osmium > 0:
                orders["ASH_COATED_OSMIUM"].append(Order("ASH_COATED_OSMIUM", osmium_px, -min(10, pos_osmium)))
            elif pos_osmium < 0:
                orders["ASH_COATED_OSMIUM"].append(Order("ASH_COATED_OSMIUM", osmium_px, min(10, -pos_osmium)))

            if pos_pepper > 0:
                orders["INTARIAN_PEPPER_ROOT"].append(Order("INTARIAN_PEPPER_ROOT", pepper_px, -min(10, pos_pepper)))
            elif pos_pepper < 0:
                orders["INTARIAN_PEPPER_ROOT"].append(Order("INTARIAN_PEPPER_ROOT", pepper_px, min(10, -pos_pepper)))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        self.strategy_name = "passive_maker"

        for product, depth in state.order_depths.items():
            pos = state.position.get(product, 0)

            product_orders: List[Order] = self.trade_simple(product, depth, pos, state.timestamp)
            self.log_strategy_activity(state.timestamp, product, product_orders, pos)
            result[product] = product_orders

        return result, 0, ""
