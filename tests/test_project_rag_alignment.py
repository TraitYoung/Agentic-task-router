from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectRagAlignmentTests(unittest.TestCase):
    def test_spec_store_has_vectorized_knowledge_index(self):
        source = (ROOT / "backend" / "memory" / "spec_store.py").read_text(encoding="utf-8")

        self.assertIn("knowledge_vectors", source)
        self.assertIn("_text_embedding", source)
        self.assertIn("_cosine_similarity", source)
        self.assertIn("search_knowledge_vector", source)

    def test_retrieval_context_indexes_project_sources(self):
        source = (ROOT / "backend" / "services" / "retrieval_context.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ensure_project_knowledge_indexed", source)

        project_source = (ROOT / "backend" / "services" / "project_knowledge.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("README.md", project_source)
        self.assertIn("docs", project_source)
        self.assertIn("backend/main.py", project_source)
        self.assertIn('"frontend"', project_source)
        self.assertIn('"app"', project_source)
        self.assertIn('"api"', project_source)


if __name__ == "__main__":
    unittest.main()
