"""Smoke tests — verify the module can be imported and instantiated."""


def test_motion_drafter_importable():
    """Verify all imports resolve — catches missing shared infrastructure."""
    from src.agents.tier2_attorney.motion_drafter import MotionDrafterAgent

    agent = MotionDrafterAgent()
    assert agent.agent_id == "motion_drafter"
    assert agent.agent_name == "Motion Drafter Agent"


def test_models_importable():
    """Verify motion models can be imported."""
    from src.models.motions import DraftMotion, MotionDrafterOutput, MotionType

    assert len(MotionType) == 5
