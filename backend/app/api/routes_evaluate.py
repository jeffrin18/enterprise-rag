from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.models import EvaluateRequest, EvaluateResponse

router = APIRouter(prefix="/evaluate", tags=["evaluate"])
settings = get_settings()


@router.post("", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    """
    Runs Ragas metrics against a (question, answer, contexts[, ground_truth])
    tuple. Useful for offline regression suites and for re-scoring answers
    returned by /query for a QA dashboard.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError:
        raise HTTPException(status_code=500, detail="Ragas is not installed in this environment.")

    data = {
        "question": [request.question],
        "answer": [request.answer],
        "contexts": [request.contexts],
    }
    metrics = [faithfulness, answer_relevancy]
    if request.ground_truth:
        data["ground_truth"] = [request.ground_truth]
        metrics += [context_precision, context_recall]

    dataset = Dataset.from_dict(data)
    try:
        result = ragas_evaluate(dataset, metrics=metrics)
        scores = result.to_pandas().iloc[0].to_dict()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ragas evaluation failed: {e}")

    faithfulness_score = float(scores.get("faithfulness", 0.0))
    recall_score = scores.get("context_recall")
    passed = (
        faithfulness_score >= settings.FAITHFULNESS_THRESHOLD
        and (recall_score is None or recall_score >= settings.CONTEXT_RECALL_THRESHOLD)
    )

    return EvaluateResponse(
        faithfulness=faithfulness_score,
        answer_relevancy=float(scores.get("answer_relevancy", 0.0)),
        context_precision=scores.get("context_precision"),
        context_recall=recall_score,
        passed=passed,
    )
