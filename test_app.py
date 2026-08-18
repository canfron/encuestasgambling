import unittest
import app


class FormTests(unittest.TestCase):
    def test_supports_single_and_multi_choice(self):
        data = app.form({"title": "Prueba", "questions": [
            {"prompt": "Una", "type": "single_choice", "options": ["A", "B"]},
            {"prompt": "Varias", "type": "multi_choice", "options": ["A", "B"]},
        ]})
        self.assertEqual([item["type"] for item in data["questions"]], ["single_choice", "multi_choice"])


if __name__ == "__main__":
    unittest.main()
