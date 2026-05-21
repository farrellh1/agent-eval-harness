def factorial(n):
    """Return n! — the product of every integer from 1 to n. By definition, 0! == 1."""
    result = 1
    for i in range(1, n):
        result *= i
    return result
