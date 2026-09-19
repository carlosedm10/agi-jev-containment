def moving_average(values: list[float], window: int) -> list[float]:
    """Return the moving average over `values` with the given window size."""
    if window <= 0:
        raise ValueError("window must be positive")
    return [sum(values[i : i + window]) / window for i in range(len(values) - window)]
