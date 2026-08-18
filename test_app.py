import unittest
import app

class TestParser(unittest.TestCase):
    def test_plain_questions(self):
        out = app.parse_questions("¿P?\n- Sí\n- No", "Prueba")
        self.assertEqual(out["questions"][0]["options"][1]["label"], "No")
    def test_two_options_required(self):
        with self.assertRaises(ValueError): app.parse_questions("¿P?\n- Sí", "Prueba")

if __name__ == "__main__": unittest.main()
