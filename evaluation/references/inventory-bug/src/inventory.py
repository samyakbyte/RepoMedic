class Inventory:
    def __init__(self):
        self.stock = {}

    def restock(self, item, qty):
        self.stock[item] = self.stock.get(item, 0) + qty

    def remove_stock(self, item, qty):
        if self.stock.get(item, 0) < qty:
            raise ValueError("insufficient stock")
        self.stock[item] -= qty

    def can_fulfill(self, item, requested):
        return self.stock.get(item, 0) >= requested
