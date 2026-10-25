from inventory import Inventory


def test_can_fulfill_exact_stock():
    inv = Inventory()
    inv.restock("widget", 5)
    assert inv.can_fulfill("widget", 5) is True


def test_can_fulfill_over_request():
    inv = Inventory()
    inv.restock("widget", 5)
    assert inv.can_fulfill("widget", 6) is False


def test_can_fulfill_zero_request():
    inv = Inventory()
    inv.restock("widget", 5)
    assert inv.can_fulfill("widget", 0) is True


def test_restock():
    inv = Inventory()
    inv.restock("widget", 3)
    inv.restock("widget", 2)
    assert inv.stock["widget"] == 5


def test_remove_stock_insufficient_raises():
    inv = Inventory()
    inv.restock("widget", 2)
    try:
        inv.remove_stock("widget", 5)
    except ValueError:
        return
    raise AssertionError("expected ValueError for insufficient stock")
