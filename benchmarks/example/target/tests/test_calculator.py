import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Calculator, subtract


class CalculatorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(Calculator().add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(subtract(5, 2), 3)


if __name__ == "__main__":
    unittest.main()
