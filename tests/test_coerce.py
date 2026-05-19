"""schemas.coerce 与 workflow 模型容错。"""

import pytest

from schemas.coerce import cap_str, list_item_to_str, normalize_str_list
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestsChangelog,
    ReverseEngineerSpec,
)


class TestCoerceHelpers:
    def test_list_item_object_to_string(self):
        item = {"name": "db", "responsibility": "IndexedDB"}
        assert list_item_to_str(item) == "db: IndexedDB"

    def test_normalize_str_list(self):
        raw = [{"name": "a", "responsibility": "b"}, "plain"]
        out = normalize_str_list(raw, limit=10, item_max=100)
        assert out == ["a: b", "plain"]


@pytest.mark.parametrize(
    "model_cls,payload",
    [
        (
            DevTaskSpec,
            {
                "goal": "g" * 3000,
                "constraints": [{"name": "c1", "description": "d1"}],
            },
        ),
        (
            DevOutline,
            {
                "modules": [{"name": "m1", "responsibility": "r1"}],
                "data_flow": "f" * 3000,
            },
        ),
        (
            DevCodeSketch,
            {"language": "TypeScript / React / Vite / Dexie.js", "code": "x" * 8000},
        ),
        (
            DevTestsChangelog,
            {
                "test_cases": [{"title": "t1", "summary": "s1"}],
                "changelog_entry": "c" * 3000,
            },
        ),
        (
            ReverseEngineerSpec,
            {
                "inferred_goal": "x" * 3000,
                "architecture_issues": [{"name": "耦合", "responsibility": "高"}],
            },
        ),
    ],
)
def test_models_coerce_oversized_and_object_lists(model_cls, payload):
    obj = model_cls.model_validate(payload)
    assert obj is not None


def test_extra_fields_ignored():
    spec = DevTaskSpec.model_validate(
        {"goal": "ok", "unknown_field": "drop me", "constraints": []}
    )
    assert spec.goal == "ok"
    assert not hasattr(spec, "unknown_field")
