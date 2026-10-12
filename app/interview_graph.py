
from typing import TypedDict, NotRequired

from langgraph.graph import END, START, StateGraph

from app.evaluation_service import evaluate_answer
from app.interview_service import generate_interview_questions


class InterviewState(TypedDict):
    job_description: str
    candidate_answer: NotRequired[str]
    question: NotRequired[str]
    expected_answer: NotRequired[str]
    topic: NotRequired[str]
    difficulty: NotRequired[str]
    score: NotRequired[int]
    strengths: NotRequired[list[str]]
    improvements: NotRequired[list[str]]
    feedback: NotRequired[str]
    sample_answer: NotRequired[str]
    next_action: NotRequired[str]


def generate_question_node(state: InterviewState) -> dict:
    """Generate one interview question from the job description."""

    result = generate_interview_questions(
        job_description=state["job_description"],
        number_of_questions=1,
    )

    question_data = result["questions"][0]

    return {
        "question": question_data["question"],
        "topic": question_data["topic"],
        "difficulty": question_data["difficulty"],
        "expected_answer": (
            f"Topic: {question_data['topic']}. "
            f"Difficulty: {question_data['difficulty']}."
        ),
    }



def evaluate_answer_node(state: InterviewState) -> dict:
    """Evaluate the candidate's answer to the generated question."""

    question = state.get("question")
    candidate_answer = state.get("candidate_answer")

    if not question:
        raise ValueError("An interview question must be generated first.")

    if not candidate_answer or not candidate_answer.strip():
        raise ValueError("Candidate answer cannot be empty.")

    result = evaluate_answer(
        question=question,
        candidate_answer=candidate_answer,
        expected_answer=state.get("expected_answer", ""),
    )

    return {
        "score": result["score"],
        "strengths": result["strengths"],
        "improvements": result["improvements"],
        "feedback": result["feedback"],
        "sample_answer": result["sample_answer"],
    }



def decide_next_action(state: InterviewState) -> dict:
    """Choose the next action based on the evaluation score."""

    if state.get("score", 0) < 6:
        action = "review_and_improve"
    else:
        action = "continue_interview"

    return {"next_action": action}


def review_and_improve_node(state: InterviewState) -> dict:
    """Add guidance when the candidate needs to improve."""

    return {
        "feedback": (
            state.get("feedback", "")
            + "\n\nRecommended next step: Study the sample answer "
            "and try answering the question again in your own words."
        ),
        "next_action": "review_and_improve",
    }


def route_after_evaluation(state: InterviewState) -> str:
    """Route the workflow according to the evaluation score."""

    return state.get("next_action", "continue_interview")


# Question generation graph
question_builder = StateGraph(InterviewState)

question_builder.add_node(
    "generate_question",
    generate_question_node,
)

question_builder.add_edge(START, "generate_question")
question_builder.add_edge("generate_question", END)

question_graph = question_builder.compile()


# Answer evaluation graph
evaluation_builder = StateGraph(InterviewState)

evaluation_builder.add_node(
    "evaluate_answer",
    evaluate_answer_node,
)
evaluation_builder.add_node(
    "decide_next_action",
    decide_next_action,
)
evaluation_builder.add_node(
    "review_and_improve",
    review_and_improve_node,
)

evaluation_builder.add_edge(START, "evaluate_answer")
evaluation_builder.add_edge(
    "evaluate_answer",
    "decide_next_action",
)

evaluation_builder.add_conditional_edges(
    "decide_next_action",
    route_after_evaluation,
    {
        "review_and_improve": "review_and_improve",
        "continue_interview": END,
    },
)

evaluation_builder.add_edge("review_and_improve", END)

evaluation_graph = evaluation_builder.compile()


# Keep the original combined graph for backward compatibility.
graph_builder = StateGraph(InterviewState)

graph_builder.add_node("generate_question", generate_question_node)
graph_builder.add_node("evaluate_answer", evaluate_answer_node)
graph_builder.add_node("decide_next_action", decide_next_action)
graph_builder.add_node("review_and_improve", review_and_improve_node)

graph_builder.add_edge(START, "generate_question")
graph_builder.add_edge("generate_question", "evaluate_answer")
graph_builder.add_edge("evaluate_answer", "decide_next_action")

graph_builder.add_conditional_edges(
    "decide_next_action",
    route_after_evaluation,
    {
        "review_and_improve": "review_and_improve",
        "continue_interview": END,
    },
)

graph_builder.add_edge("review_and_improve", END)

interview_graph = graph_builder.compile()
