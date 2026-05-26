from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "backend" / "schemas" / "workflows.py"
ARTIFACT_PACK = ROOT / "backend" / "schemas" / "artifact_pack.py"


def test_engineering_handoff_contract_is_defined_for_downstream_agents():
    source = WORKFLOWS.read_text(encoding="utf-8")

    assert "ENGINEERING_HANDOFF_CONTRACT" in source
    assert "Agent Handoff Contract" in source
    assert "boundaries" in source
    assert "tests" in source
    assert "Do not start coding until" in source


def test_handoff_contract_is_in_copyable_prompts_and_artifact():
    workflows = WORKFLOWS.read_text(encoding="utf-8")
    artifact = ARTIFACT_PACK.read_text(encoding="utf-8")

    assert "ENGINEERING_HANDOFF_CONTRACT" in artifact
    assert "ENGINEERING_HANDOFF_CONTRACT" in workflows
    assert "ENGINEERING_HANDOFF_CONTRACT" in workflows.split("def to_implementation_prompt", 1)[1]
    assert "ENGINEERING_HANDOFF_CONTRACT" in workflows.split("def to_test_prompt", 1)[1]
    assert "ENGINEERING_HANDOFF_CONTRACT" in artifact.split("sections = [", 1)[1]
    assert "stop_headings" in artifact
    assert '"## Starter Code"' in artifact


if __name__ == "__main__":
    test_engineering_handoff_contract_is_defined_for_downstream_agents()
    test_handoff_contract_is_in_copyable_prompts_and_artifact()
