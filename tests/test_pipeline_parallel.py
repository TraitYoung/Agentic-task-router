from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PipelineParallelScriptTests(unittest.TestCase):
    def test_core_pipeline_runs_implementation_and_delivery_in_parallel(self):
        source = (ROOT / "backend" / "agents" / "dev_pipeline" / "orchestrator.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ThreadPoolExecutor", source)
        self.assertIn('"implementation"', source)
        self.assertIn('"delivery"', source)
        self.assertIn("as_completed", source)
        self.assertLess(source.index("run_implementation_step"), source.index("run_test_code_step"))
        self.assertLess(source.index("run_delivery_step"), source.index("run_test_code_step"))

    def test_delivery_prompt_no_longer_requires_implementation_sketch(self):
        source = (ROOT / "backend" / "agents" / "dev_pipeline" / "step_agents.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("def run_delivery_step", source)
        delivery_fn = source[source.index("def run_delivery_step") : source.index("def _test_code_context")]
        self.assertNotIn("sketch: DevCodeSketch", delivery_fn)
        self.assertNotIn('"sketch": sketch.model_dump()', delivery_fn)


if __name__ == "__main__":
    unittest.main()
