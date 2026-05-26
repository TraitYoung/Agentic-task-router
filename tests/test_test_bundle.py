"""DevTestBundle schema 与 coerce。"""

from schemas.workflows import DevTestBundle, DevTestFile


def test_dev_test_bundle_accepts_files():
    bundle = DevTestBundle.model_validate(
        {
            "files": [
                {"path": "tests/test_app.py", "code": "def test_ok(): assert True"},
            ]
        }
    )
    assert len(bundle.files) == 1
    assert bundle.files[0].path == "tests/test_app.py"


def test_dev_test_bundle_caps_file_count():
    raw = {"files": [{"path": f"t{i}.py", "code": "pass"} for i in range(8)]}
    bundle = DevTestBundle.model_validate(raw)
    assert len(bundle.files) <= 2
