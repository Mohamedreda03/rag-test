"""User-facing progress messages for pipeline status events.

Status messages are shown directly to end users, so they are written in
Egyptian Arabic (matching the answer language), while all code stays in English.
The searching message adapts to the detected question type so the progress
feels relevant to the actual task.
"""

import json

_SEARCHING_BY_TYPE = {
    "simple": "بدور في المحتوى على إجابة سؤالك...",
    "multi_part": "سؤالك فيه {count} أجزاء، بدور على إجابة كل جزء لوحده في المحتوى...",
    "comparative": "بجمع المعلومات عن كل عنصر من اللي عاوز تقارن بينهم عشان المقارنة تطلع دقيقة...",
    "inferential": "سؤالك محتاج استنتاج، فبجمع الحقائق المرتبطة من المحتوى الأول...",
}

_STAGE_MESSAGES = {
    "understanding": "بقرأ سؤالك كويس وبحدد نوعه وأجزائه...",
    "ranking": "براجع المقاطع اللي لقيتها وبختار أنسبها لسؤالك...",
    "generating": "بجهزلك الإجابة النهائية مدعومة بالمصادر...",
}


def status_event(
    stage: str, question_type: str | None = None, sub_count: int = 0
) -> dict[str, str]:
    """Build an SSE 'status' event with a task-appropriate Egyptian Arabic message."""
    if stage == "searching":
        template = _SEARCHING_BY_TYPE.get(question_type or "simple", _SEARCHING_BY_TYPE["simple"])
        message = template.format(count=sub_count)
    else:
        message = _STAGE_MESSAGES[stage]
    return {
        "event": "status",
        "data": json.dumps({"stage": stage, "message": message}, ensure_ascii=False),
    }
