"""Тесты эмулятора оболочки."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(os.path.dirname(TESTS_DIR), "src")
sys.path.insert(0, SOURCE_DIR)
