# Example file: example.py

def greet(name: str) -> str:
    return "Hello, " + name

def add(x: int, y: int) -> int:
    return x + y

result = greet(123)  # This will cause a mypy error since 123 is not a str
sum_value = add(2, "3")  # This will cause a mypy error since "3" is not an int
