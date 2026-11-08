"""User profile API."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.schemas.profile import (
    AssessmentQuestionResponse,
    AssessmentSubmitRequest,
    BehaviorAvailabilityResponse,
    BehaviorGenerateResponse,
    BehaviorRefreshResponse,
    DialogueMessageRequest,
    DialogueMessageResponse,
    DialogueStartResponse,
    DialogueSwitchDimensionRequest,
    ProfileDimensionUpdateRequest,
    ProfileModesMetaResponse,
    ProfileResponse,
    QuestionnaireItemResponse,
    QuestionnaireSubmitRequest,
)
from app.services.profile_assessment_service import ProfileAssessmentService
from app.services.profile_behavior_service import ProfileBehaviorService
from app.services.profile_questionnaire_service import ProfileQuestionnaireService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("", summary="获取用户画像", response_model=ApiResponse[ProfileResponse])
def get_profile(current_user: CurrentUser, db: DbSession) -> ApiResponse[ProfileResponse]:
    """获取当前用户完整画像（含6维核心数据）。"""
    data = ProfileService(db).get_profile_detail(current_user)
    return ApiResponse.success(data)


@router.put("/dimensions", summary="更新画像维度", response_model=ApiResponse[ProfileResponse])
def update_dimension(
    req: ProfileDimensionUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ProfileResponse]:
    """手动更新单个画像维度。"""
    data = ProfileService(db).update_dimension(current_user, req)
    return ApiResponse.success(data)


@router.post("/dialogue/start", summary="开始画像对话", response_model=ApiResponse[DialogueStartResponse])
async def start_dialogue(current_user: CurrentUser, db: DbSession) -> ApiResponse[DialogueStartResponse]:
    """启动对话式画像构建会话。"""
    data = await ProfileService(db).start_dialogue(current_user)
    return ApiResponse.success(data)


@router.post(
    "/dialogue/{session_no}/message",
    summary="发送画像对话消息",
    response_model=ApiResponse[DialogueMessageResponse],
)
async def send_dialogue_message(
    session_no: str,
    req: DialogueMessageRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[DialogueMessageResponse]:
    """发送对话消息，自动提取维度并更新画像。"""
    data = await ProfileService(db).send_dialogue_message(current_user, session_no, req)
    return ApiResponse.success(data)


@router.post("/dialogue/{session_no}/message/stream", summary="发送画像对话消息（SSE流式）")
async def stream_dialogue_message(
    session_no: str,
    req: DialogueMessageRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    """流式推送助手提问，便于语音通话实时字幕。"""
    import json

    from fastapi.responses import StreamingResponse

    service = ProfileService(db)
    SSE_HEADERS = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    async def event_stream():
        async for event_type, payload in service.stream_dialogue_message(
            current_user, session_no, req
        ):
            yield f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers=SSE_HEADERS,
    )


@router.post(
    "/dialogue/{session_no}/switch-dimension",
    summary="对话模式维度跳转",
    response_model=ApiResponse[DialogueStartResponse],
)
async def switch_dialogue_dimension(
    session_no: str,
    req: DialogueSwitchDimensionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[DialogueStartResponse]:
    """用户主动切换采集维度，AI 承接新维度提问。"""
    data = await ProfileService(db).switch_dialogue_dimension(current_user, session_no, req.dimension_code)
    return ApiResponse.success(data)


@router.get("/questionnaire", summary="获取结构化问卷", response_model=ApiResponse[list[QuestionnaireItemResponse]])
def get_questionnaire(_: CurrentUser, db: DbSession) -> ApiResponse[list[QuestionnaireItemResponse]]:
    items = ProfileQuestionnaireService(db).get_items()
    return ApiResponse.success([QuestionnaireItemResponse.model_validate(i) for i in items])


@router.post("/questionnaire/submit", summary="提交问卷画像", response_model=ApiResponse[ProfileResponse])
def submit_questionnaire(
    req: QuestionnaireSubmitRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ProfileResponse]:
    data = ProfileQuestionnaireService(db).submit(current_user, req)
    return ApiResponse.success(data)


@router.get("/assessment/bank", summary="获取自适应测评题库", response_model=ApiResponse[list[AssessmentQuestionResponse]])
def get_assessment_bank(_: CurrentUser, db: DbSession) -> ApiResponse[list[AssessmentQuestionResponse]]:
    items = ProfileAssessmentService(db).get_bank()
    return ApiResponse.success([AssessmentQuestionResponse.model_validate(i) for i in items])


@router.post("/assessment/submit", summary="提交自适应测评", response_model=ApiResponse[ProfileResponse])
def submit_assessment(
    req: AssessmentSubmitRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[ProfileResponse]:
    data = ProfileAssessmentService(db).submit(current_user, req)
    return ApiResponse.success(data)


@router.get("/behavior/availability", summary="行为画像数据可用性", response_model=ApiResponse[BehaviorAvailabilityResponse])
def behavior_availability(current_user: CurrentUser, db: DbSession) -> ApiResponse[BehaviorAvailabilityResponse]:
    info = ProfileBehaviorService(db).check_availability(current_user)
    return ApiResponse.success(BehaviorAvailabilityResponse.model_validate(info))


@router.post("/behavior/refresh", summary="静默刷新行为画像（动态调整）", response_model=ApiResponse[BehaviorRefreshResponse])
def refresh_behavior_profile(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[BehaviorRefreshResponse]:
    """根据最新学习行为加权更新画像，6 小时内节流。"""
    result = ProfileBehaviorService(db).refresh_from_behavior(current_user)
    return ApiResponse.success(BehaviorRefreshResponse.model_validate(result))


@router.post("/behavior/generate", summary="基于学习行为生成画像", response_model=ApiResponse[BehaviorGenerateResponse])
def generate_behavior_profile(
    current_user: CurrentUser,
    db: DbSession,
) -> ApiResponse[BehaviorGenerateResponse]:
    data = ProfileBehaviorService(db).generate(current_user)
    return ApiResponse.success(data)


@router.get("/modes/meta", summary="画像构建模式元信息", response_model=ApiResponse[ProfileModesMetaResponse])
def profile_modes_meta(current_user: CurrentUser, db: DbSession) -> ApiResponse[ProfileModesMetaResponse]:
    svc = ProfileService(db)
    behavior = ProfileBehaviorService(db).check_availability(current_user)
    detail = svc.get_profile_detail(current_user)
    return ApiResponse.success(
        ProfileModesMetaResponse(
            behavior_available=behavior["has_data"],
            has_profile_data=detail.is_profile_built,
            preferred_mode=None,
        )
    )
