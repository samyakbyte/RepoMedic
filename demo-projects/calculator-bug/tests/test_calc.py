from calc import add, subtract, multiply, apply_discount


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 2) == 3


def test_multiply():
    assert multiply(4, 3) == 12


def test_apply_discount_zero_percent():
    assert apply_discount(100, 0) == 100


def test_apply_discount_full_percent():
    assert apply_discount(100, 100) == 0


def test_apply_discount_partial():
    assert apply_discount(200, 10) == 180
