print('Это файл', __name__)


# file_11 (текущий файл) находится в том же каталоге, что и file_12, поэтому ставится одна точка
from .file_12 import num


def some_func(n: int) -> float:
    return (n + n) / n**n


result = some_func(num)