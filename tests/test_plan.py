"""
Unit tests for the Planner's context window exceeded handling.

Verifies that ContextWindowExceededError triggers trajectory truncation
and that a ValueError is raised when truncation cannot resolve the issue.
"""

from unittest.mock import MagicMock, patch

import dspy
import pytest
from litellm import ContextWindowExceededError

from chatdku.core.dspy_classes.plan import Planner


def _make_planner():
    """Create a Planner with a dummy tool."""
    dummy_tool = dspy.Tool(
        func=lambda query: "result",
        name="search",
        desc="Search for information",
        args={"query": {"type": "string", "desc": "search query"}},
    )
    return Planner(tools=[dummy_tool], max_iterations=5)


class TestContextWindowExceeded:
    def test_truncation_then_success(self):
        """ContextWindowExceededError on first call triggers truncation, second call succeeds."""
        planner = _make_planner()

        mock_module = MagicMock()
        fake_result = MagicMock()
        mock_module.side_effect = [
            ContextWindowExceededError(
                message="context window exceeded",
                model="test-model",
                llm_provider="test",
            ),
            fake_result,
        ]

        # Provide a trajectory with enough entries to truncate (>= 4 keys)
        trajectory = {
            "thought_0": "thinking",
            "tool_name_0": "search",
            "tool_args_0": '{"query": "test"}',
            "observation_0": "some result",
            "thought_1": "more thinking",
            "tool_name_1": "search",
            "tool_args_1": '{"query": "test2"}',
            "observation_1": "another result",
        }

        with patch.object(planner, "truncate_trajectory") as mock_truncate:
            mock_truncate.return_value = (
                "summary of discarded",
                {
                    "thought_1": "more thinking",
                    "tool_name_1": "search",
                    "tool_args_1": '{"query": "test2"}',
                    "observation_1": "another result",
                },
            )

            result = planner._call_with_potential_trajectory_truncation(
                mock_module, trajectory, current_user_message="hello"
            )

        assert result == fake_result
        mock_truncate.assert_called_once()
        assert planner.trajectory_summary == "summary of discarded"

    def test_raises_value_error_after_3_failures(self):
        """ValueError is raised after 3 consecutive ContextWindowExceededErrors."""
        planner = _make_planner()

        mock_module = MagicMock()
        mock_module.side_effect = ContextWindowExceededError(
            message="context window exceeded",
            model="test-model",
            llm_provider="test",
        )

        trajectory = {
            "thought_0": "t",
            "tool_name_0": "search",
            "tool_args_0": "{}",
            "observation_0": "r",
            "thought_1": "t",
            "tool_name_1": "search",
            "tool_args_1": "{}",
            "observation_1": "r",
            "thought_2": "t",
            "tool_name_2": "search",
            "tool_args_2": "{}",
            "observation_2": "r",
        }

        with patch.object(planner, "truncate_trajectory") as mock_truncate:
            # Each truncation removes 4 keys but error persists
            mock_truncate.side_effect = [
                ("summary1", {k: v for k, v in list(trajectory.items())[4:]}),
                ("summary2", {k: v for k, v in list(trajectory.items())[8:]}),
                ("summary3", {}),
            ]

            with pytest.raises(
                ValueError, match="context window was exceeded even after 3 attempts"
            ):
                planner._call_with_potential_trajectory_truncation(
                    mock_module, trajectory, current_user_message="hello"
                )

        assert mock_truncate.call_count == 3
