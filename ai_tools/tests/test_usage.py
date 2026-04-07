import unittest
from ai_tools.usage import UsageTracker

class TestUsageTracker(unittest.TestCase):
    def test_update_from_dict(self):
        tracker = UsageTracker()
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "cost": 0.05,
            "completion_tokens_details": {"reasoning_tokens": 5}
        }
        tracker.update(usage)
        self.assertEqual(tracker.total_prompt_tokens, 10)
        self.assertEqual(tracker.total_completion_tokens, 20)
        self.assertEqual(tracker.total_tokens, 30)
        self.assertEqual(tracker.total_cost, 0.05)
        self.assertEqual(tracker.total_reasoning_tokens, 5)

    def test_update_from_object(self):
        tracker = UsageTracker()
        class Usage:
            def __init__(self):
                self.prompt_tokens = 15
                self.completion_tokens = 25
                self.total_tokens = 40
                self.cost = 0.1
                self.model_extra = {"cost": 0.12}
                class Details:
                    def __init__(self):
                        self.reasoning_tokens = 8
                self.completion_tokens_details = Details()

        tracker.update(Usage())
        self.assertEqual(tracker.total_prompt_tokens, 15)
        self.assertEqual(tracker.total_completion_tokens, 25)
        self.assertEqual(tracker.total_tokens, 40)
        self.assertEqual(tracker.total_cost, 0.12)  # model_extra takes precedence
        self.assertEqual(tracker.total_reasoning_tokens, 8)

    def test_aggregate_from(self):
        tracker1 = UsageTracker()
        tracker2 = UsageTracker()
        
        tracker1.update({"prompt_tokens": 10, "cost": 0.1})
        tracker2.update({"prompt_tokens": 20, "cost": 0.2})
        
        tracker1.aggregate_from(tracker2)
        
        self.assertEqual(tracker1.total_prompt_tokens, 30)
        self.assertAlmostEqual(tracker1.total_cost, 0.3)

    def test_reset(self):
        tracker = UsageTracker()
        tracker.update({"prompt_tokens": 10, "cost": 0.1})
        tracker.reset()
        self.assertEqual(tracker.total_prompt_tokens, 0)
        self.assertEqual(tracker.total_cost, 0.0)

    def test_snapshot(self):
        tracker = UsageTracker()
        tracker.update({"prompt_tokens": 10, "cost": 0.1})
        snapshot = tracker.snapshot
        self.assertEqual(snapshot["prompt_tokens"], 10)
        self.assertEqual(snapshot["cost"], 0.1)

if __name__ == "__main__":
    unittest.main()
