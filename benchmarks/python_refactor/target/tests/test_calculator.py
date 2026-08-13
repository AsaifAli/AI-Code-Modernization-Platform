import unittest
from calculator import Calculator


class CalculatorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(Calculator().add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(Calculator().subtract(5, 2), 3)


if __name__ == "__main__":
    unittest.main()
