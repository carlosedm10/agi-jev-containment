from app.calc import moving_average


def test_moving_average_basic():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_moving_average_full_window():
    assert moving_average([2, 4], 2) == [3.0]


def test_moving_average_window_one():
    assert moving_average([5, 7, 9], 1) == [5.0, 7.0, 9.0]
