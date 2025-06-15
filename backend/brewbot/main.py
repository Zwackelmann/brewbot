from brewbot.config import load_config
from pydantic import validate_call


def main():
    a = A()
    a.test([1, 2, 3.5])


class A:
    def __init__(self):
        pass

    @validate_call
    def test(self, a: list[int]):
        print(a)

if __name__ == "__main__":
    main()
