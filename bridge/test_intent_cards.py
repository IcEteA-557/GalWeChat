"""Intent-card span and per-batch context. Standard library only."""

import unittest

from intent_card_contracts import intent_card_batches, intent_card_targets


def window():
    rows = [{"id": f"c{i}", "side": "self" if i % 2 == 0 else "other", "text": f"ctx{i}"}
            for i in range(25)]
    rows.append({"id": "start", "side": "other", "text": "开始"})
    for i in range(9):
        rows.append({"id": f"s{i}", "side": "self", "text": f"me{i}"})
        rows.append({"id": f"t{i}", "side": "other", "text": f"later{i}"})
    rows.append({"id": "tail", "side": "self", "text": "最新的我"})
    return rows


class IntentCardSpanTests(unittest.TestCase):
    def test_start_runs_through_the_latest_other_text_and_context_precedes_each_batch(self):
        rows = window()
        selected = intent_card_targets(rows, "start")
        self.assertEqual([item["id"] for item in selected],
                         ["start", *(f"t{i}" for i in range(9))])
        self.assertNotIn("c1", [item["id"] for item in selected])

        batches = intent_card_batches(rows, selected)
        self.assertEqual(len(batches), 2)
        first_batch, first_wire = batches[0]
        self.assertEqual([item["id"] for item in first_batch],
                         ["start", *(f"t{i}" for i in range(7))])
        first_ids = [item["id"] for item in first_wire]
        self.assertEqual(first_ids[:20], [f"c{i}" for i in range(5, 25)])
        self.assertNotIn("tail", first_ids)
        self.assertNotIn("t7", first_ids)
        self.assertEqual(first_wire[20]["sender"], "OTHER")

        second_batch, second_wire = batches[1]
        self.assertEqual([item["id"] for item in second_batch], ["t7", "t8"])
        second_ids = [item["id"] for item in second_wire]
        start = next(index for index, item in enumerate(rows) if item["id"] == "t7")
        self.assertEqual(second_ids[:20], [item["id"] for item in rows[start - 20:start]])
        self.assertEqual(second_ids[-2:], ["t7", "t8"])
        self.assertNotIn("tail", second_ids)
        tail_window = [item["id"] for item in rows[-20:]]
        self.assertIn("tail", tail_window)
        self.assertNotEqual(second_ids[:20], tail_window)

    def test_missing_or_own_start_is_outside_the_window(self):
        rows = window()
        with self.assertRaisesRegex(ValueError, "intent-card-start-outside-window"):
            intent_card_targets(rows, "missing")
        with self.assertRaisesRegex(ValueError, "intent-card-start-outside-window"):
            intent_card_targets(rows, "s0")


if __name__ == "__main__":
    unittest.main()
