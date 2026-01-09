from typing import  Callable, Any, Iterable, TypeVar
from functools import reduce, partial

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")

def pipe(value: T, *functions: Callable[[Any], Any]) -> Any:
    """
    Pipes a value through a sequence of functions.
    Equivalent to f_n(...(f_2(f_1(value)))...)
    """
    return reduce(lambda x, f: f(x), functions, value)

def compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Composes functions from right to left.
    Returns a new function that applies the composition.
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)

def map_c(func: Callable[[T], U]) -> Callable[[Iterable[T]], Iterable[U]]:
    """
    Curried map function.
    """
    return lambda iterable: map(func, iterable)

def filter_c(predicate: Callable[[T], bool]) -> Callable[[Iterable[T]], Iterable[T]]:
    """
    Curried filter function.
    """
    return lambda iterable: filter(predicate, iterable)
