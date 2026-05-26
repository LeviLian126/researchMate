from dataclasses import dataclass
from re import sub

from researchmate_api.schemas.common import ExecutionPlan, SourceMode, TaskType


# 表示 slash command 与 Mode selector 合并后的执行意图。
@dataclass(frozen=True)
class ResolvedIntent:
    plan: ExecutionPlan
    clean_message: str
    router_reason: str


SLASH_TO_MODE: dict[str, tuple[SourceMode, TaskType, str]] = {
    "/study": (SourceMode.LOCAL_ONLY, TaskType.ANSWER, "Slash /study forces local_only answer."),
    "/search": (SourceMode.WEB_ONLY, TaskType.ANSWER, "Slash /search forces web_only answer."),
    "/hybrid": (SourceMode.HYBRID, TaskType.ANSWER, "Slash /hybrid forces hybrid answer."),
    "/quiz": (SourceMode.LOCAL_ONLY, TaskType.QUIZ, "Slash /quiz forces local_only quiz."),
}


# 从用户消息和 UI Mode selector 解析 source policy。
def resolve_intent(message: str, selected_mode: SourceMode, default_task: TaskType) -> ResolvedIntent:
    normalized = message.strip()
    first_token = normalized.split(maxsplit=1)[0].lower() if normalized else ""

    if first_token in SLASH_TO_MODE:
        source_mode, task_type, reason = SLASH_TO_MODE[first_token]
        clean_message = normalized[len(first_token) :].strip() or first_token
    else:
        task_type = default_task
        if selected_mode == SourceMode.AUTO:
            source_mode = SourceMode.LOCAL_ONLY
            reason = "Auto defaults to local_only to control cost and latency."
        else:
            source_mode = selected_mode
            reason = "UI Mode selector overrides auto routing."
        clean_message = normalized

    allowed_tools = _allowed_tools_for(source_mode, task_type)
    return ResolvedIntent(
        plan=ExecutionPlan(
            source_mode=source_mode,
            task_type=task_type,
            allowed_tools=allowed_tools,
            requires_local_docs=source_mode in {SourceMode.LOCAL_ONLY, SourceMode.HYBRID},
            requires_web=source_mode == SourceMode.WEB_ONLY,
            output_schema="QuizSet" if task_type == TaskType.QUIZ else "GroundedAnswer",
        ),
        clean_message=clean_message,
        router_reason=reason,
    )


# 校验实际工具调用没有越过 source policy。
def validate_tool_policy(plan: ExecutionPlan, tool_names: list[str]) -> dict[str, object]:
    allowed = set(plan.allowed_tools)
    denied = sorted(name for name in tool_names if name not in allowed)
    return {
        "passed": denied == [],
        "denied_tools": denied,
        "allowed_tools": sorted(allowed),
    }


# 移除 slash command，便于 UI 和 trace 展示安全摘要。
def strip_slash_command(message: str) -> str:
    return sub(r"^/(study|search|hybrid|quiz)\s*", "", message.strip(), flags=0).strip()


# 根据 Mode 和 Task 生成最小工具白名单。
def _allowed_tools_for(source_mode: SourceMode, task_type: TaskType) -> list[str]:
    tools: list[str] = []
    if source_mode in {SourceMode.LOCAL_ONLY, SourceMode.HYBRID}:
        tools.append("query_local_docs")
    if source_mode == SourceMode.WEB_ONLY:
        tools.extend(["search_web", "read_url"])
    if source_mode == SourceMode.HYBRID:
        tools.extend(["search_web", "read_url", "evidence_fusion"])
    if task_type == TaskType.QUIZ:
        tools.extend(["generate_quiz", "save_quiz"])
    else:
        tools.append("generate_answer")
    return tools
