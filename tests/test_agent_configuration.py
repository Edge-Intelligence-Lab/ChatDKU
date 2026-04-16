"""Tests that verify the Planner + Executor are configured correctly for
policy-aware, agenda-extending course recommendations.

These are structural/configuration tests — they do not invoke any LLM or
external services.
"""

import pytest

from chatdku.core.dspy_classes.executor import AssessSignature, Executor
from chatdku.core.dspy_classes.plan import PLANNER_DEMOS, PlannerSignature


# ---------------------------------------------------------------------------
# Planner configuration tests
# ---------------------------------------------------------------------------


class TestPlannerConfiguration:
    """Verify the Planner is configured for policy-first course planning."""

    def test_planner_signature_has_available_tools_field(self):
        """Planner must expose tool descriptions so it can include them in plans."""
        fields = PlannerSignature.input_fields
        assert "available_tools" in fields

    def test_planner_instructions_require_policy_retrieval_before_recommender(self):
        """Planner docstring must instruct: retrieve policies FIRST, then CourseRecommender."""
        instructions = PlannerSignature.__doc__
        assert instructions is not None
        # Should mention policy/year retrieval
        assert any(
            kw in instructions.lower()
            for kw in ("policy", "policies", "mandatory courses", "year-specific")
        ), "Planner must instruct Executor to retrieve year-specific policies"
        # Should still mention CourseRecommender
        assert "CourseRecommender" in instructions, (
            "Planner must still reference CourseRecommender as the baseline tool"
        )

    def test_planner_instructions_mention_vector_or_keyword_retriever_for_policies(self):
        """Planner must name VectorRetriever or KeywordRetriever for policy lookup."""
        instructions = PlannerSignature.__doc__ or ""
        assert "VectorRetriever" in instructions or "KeywordRetriever" in instructions, (
            "Planner must instruct use of VectorRetriever/KeywordRetriever for policy lookup"
        )

    def test_planner_missing_info_demo_asks_for_all_three(self):
        """The 'missing info' demo must ask for major, year, and completed courses."""
        missing_info_demo = next(
            (d for d in PLANNER_DEMOS if d.action_type == "send_message"), None
        )
        assert missing_info_demo is not None, "PLANNER_DEMOS must have a send_message example"
        action = missing_info_demo.action.lower()
        assert "major" in action, "Missing-info message must ask for major"
        assert any(kw in action for kw in ("year", "matriculation", "class of")), (
            "Missing-info message must ask for year of matriculation"
        )
        assert any(kw in action for kw in ("completed", "taken", "taking")), (
            "Missing-info message must ask for completed courses"
        )

    def test_planner_schedule_demo_is_policy_first(self):
        """The full schedule planning demo must mention policy retrieval before CourseRecommender."""
        # Find the demo that has all three pieces of info (plan action, mentions Data Science)
        plan_demos = [d for d in PLANNER_DEMOS if d.action_type == "plan"]
        schedule_demo = next(
            (d for d in plan_demos if "Class of" in d.current_user_message), None
        )
        assert schedule_demo is not None, (
            "PLANNER_DEMOS must include a complete schedule planning example with class year"
        )
        action = schedule_demo.action
        # Policy step should appear before CourseRecommender call in the action text
        policy_keywords = ["policy", "policies", "mandatory", "retrieve", "VectorRetriever",
                           "KeywordRetriever", "year-specific", "requirements"]
        has_policy_step = any(kw.lower() in action.lower() for kw in policy_keywords)
        assert has_policy_step, (
            f"Schedule planning demo must include a policy-retrieval step.\nAction:\n{action}"
        )
        policy_pos = min(
            (action.lower().find(kw.lower()) for kw in policy_keywords if kw.lower() in action.lower()),
            default=-1,
        )
        recommender_pos = action.find("CourseRecommender")
        assert recommender_pos != -1, "Demo must mention CourseRecommender"
        assert policy_pos < recommender_pos, (
            "Policy retrieval step must come BEFORE CourseRecommender in the demo plan"
        )


# ---------------------------------------------------------------------------
# Executor configuration tests
# ---------------------------------------------------------------------------


class TestExecutorConfiguration:
    """Verify the Executor supports dynamic agenda extensions."""

    def test_assess_signature_has_agenda_extensions_output(self):
        """AssessSignature must have an agenda_extensions output field."""
        output_fields = AssessSignature.output_fields
        assert "agenda_extensions" in output_fields, (
            "AssessSignature must have agenda_extensions output to communicate "
            "new investigation areas discovered during execution"
        )

    def test_assess_signature_has_current_agenda_not_plan(self):
        """AssessSignature uses 'current_agenda' (not 'plan') as the input field name."""
        input_fields = AssessSignature.input_fields
        assert "current_agenda" in input_fields, (
            "AssessSignature must use 'current_agenda' (not 'plan') to indicate "
            "the agenda can grow beyond the original plan"
        )
        assert "plan" not in input_fields, (
            "AssessSignature must not use the old 'plan' field name"
        )

    def test_assess_signature_decision_field_exists_as_output(self):
        """AssessSignature must have a 'decision' output field."""
        assert "decision" in AssessSignature.output_fields, (
            "AssessSignature must define a 'decision' output field"
        )
        # Verify it is not accidentally an input field.
        assert "decision" not in AssessSignature.input_fields

    def test_assess_signature_docstring_mentions_agenda_extensions(self):
        """AssessSignature docstring must describe discovering new investigation areas."""
        doc = AssessSignature.__doc__ or ""
        assert any(
            kw in doc.lower()
            for kw in ("new investigation", "agenda extension", "revealed", "discovered")
        ), "AssessSignature docstring must explain when to extend the agenda"

    def test_executor_get_token_limits_accepts_current_agenda(self, tmp_path):
        """Executor.get_token_limits must accept 'current_agenda' (not 'plan')."""
        # Build a minimal Executor with a trivial tool.
        def dummy_tool(query: str) -> str:
            """A dummy tool for testing. Args: query (str): The query."""
            return "dummy"

        try:
            executor = Executor([dummy_tool], max_iterations=1)
            # Should not raise — the old code used 'plan' which would break here.
            limits = executor.get_token_limits(
                current_agenda="test plan",
                current_user_message="test",
                conversation_history="",
                conversation_summary="",
                trajectory="",
                assessment="",
            )
            assert isinstance(limits, dict)
            assert len(limits) > 0
        except Exception as e:
            pytest.fail(f"get_token_limits with current_agenda raised: {e}")

    def test_executor_max_iterations_default_is_five_or_more(self):
        """Executor default max_iterations should be >= 5 for policy-aware planning."""
        import inspect
        sig = inspect.signature(Executor.__init__)
        default = sig.parameters["max_iterations"].default
        assert default >= 5, (
            f"Executor default max_iterations is {default}, expected >= 5 for policy-first plans "
            "(policy retrieval + CourseRecommender + potential extensions require more iterations)"
        )
