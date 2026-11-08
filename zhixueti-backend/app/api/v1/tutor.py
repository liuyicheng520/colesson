"""Tutor API — personalized multimodal Q&A."""



import json
from urllib.parse import quote



from fastapi import APIRouter, File, UploadFile

from fastapi.responses import Response, StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Type": "text/event-stream; charset=utf-8",
}



from app.core.deps import CurrentUser, DbSession

from app.core.response import ApiResponse

from app.schemas.tutor import (

    TutorBindDocumentsRequest,

    TutorDocumentItem,

    TutorDocumentUploadResponse,

    TutorLectureGenerateRequest,

    TutorLectureSideAskRequest,

    TutorLectureQuizSubmitRequest,

    TutorLectureSummary,

    TutorMessageRequest,

    TutorMessageResponse,

    TutorMultimodalRequest,

    TutorMultimodalResponse,

    TutorSessionCreateRequest,

    TutorSessionResponse,

    TutorSessionSettingsRequest,

)

from app.services.tutor_service import TutorService



router = APIRouter()





@router.post("/sessions", summary="创建辅导会话", response_model=ApiResponse[TutorSessionResponse])

async def create_session(

    req: TutorSessionCreateRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorSessionResponse]:

    data = await TutorService(db).create_session(current_user, req)

    return ApiResponse.success(data)





@router.get("/sessions", summary="辅导会话列表", response_model=ApiResponse[list[TutorSessionResponse]])

def list_sessions(current_user: CurrentUser, db: DbSession) -> ApiResponse[list[TutorSessionResponse]]:

    return ApiResponse.success(TutorService(db).list_sessions(current_user))





@router.get("/sessions/{session_no}", summary="辅导会话详情", response_model=ApiResponse[TutorSessionResponse])

def get_session(

    session_no: str, current_user: CurrentUser, db: DbSession

) -> ApiResponse[TutorSessionResponse]:

    return ApiResponse.success(TutorService(db).get_session(current_user, session_no))





@router.delete("/sessions/{session_no}", summary="删除辅导会话", response_model=ApiResponse[None])

def delete_session(

    session_no: str, current_user: CurrentUser, db: DbSession

) -> ApiResponse[None]:

    TutorService(db).delete_session(current_user, session_no)

    return ApiResponse.success(None)





@router.put("/sessions/{session_no}/documents", summary="绑定会话文档", response_model=ApiResponse[TutorSessionResponse])

def bind_documents(

    session_no: str,

    req: TutorBindDocumentsRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorSessionResponse]:

    data = TutorService(db).update_session_settings(current_user, session_no, document_ids=req.document_ids)

    return ApiResponse.success(data)





@router.put("/sessions/{session_no}/settings", summary="更新会话设置（深度/联网等实时生效）", response_model=ApiResponse[TutorSessionResponse])

def update_settings(

    session_no: str,

    req: TutorSessionSettingsRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorSessionResponse]:

    data = TutorService(db).update_session_settings(

        current_user,

        session_no,

        document_ids=req.document_ids,

        deep_mode=req.deep_mode,

        web_search_enabled=req.web_search_enabled,

        answer_detail=req.answer_detail,

        show_steps=req.show_steps,

        profile_adapt_enabled=req.profile_adapt_enabled,

        tutor_mode=req.tutor_mode,

    )

    return ApiResponse.success(data)





@router.post(

    "/sessions/{session_no}/documents/upload",

    summary="上传答疑文档（会话级）",

    response_model=ApiResponse[TutorDocumentUploadResponse],

)

async def upload_session_document(

    session_no: str,

    current_user: CurrentUser,

    db: DbSession,

    file: UploadFile = File(...),

) -> ApiResponse[TutorDocumentUploadResponse]:

    data = await file.read()

    result = TutorService(db).upload_session_document(

        current_user, session_no, file.filename or "document.pdf", data

    )

    return ApiResponse.success(TutorDocumentUploadResponse(**result))





@router.get(

    "/sessions/{session_no}/documents",

    summary="当前会话文档列表",

    response_model=ApiResponse[list[TutorDocumentItem]],

)

def list_session_documents(

    session_no: str, current_user: CurrentUser, db: DbSession

) -> ApiResponse[list[TutorDocumentItem]]:

    items = TutorService(db).list_session_documents(current_user, session_no)

    return ApiResponse.success([TutorDocumentItem(**i) for i in items])





@router.delete(

    "/sessions/{session_no}/documents/{doc_id}",

    summary="删除会话文档",

    response_model=ApiResponse[TutorSessionResponse],

)

def delete_session_document(

    session_no: str,

    doc_id: str,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorSessionResponse]:

    data = TutorService(db).delete_session_document(current_user, session_no, doc_id)

    return ApiResponse.success(data)





@router.post(

    "/sessions/{session_no}/lecture/generate",

    summary="生成沉浸式讲解",

)

async def generate_immersive_lecture(

    session_no: str,

    req: TutorLectureGenerateRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[dict]:

    data = await TutorService(db).generate_immersive_lecture(

        current_user, session_no, req.topic, req.source_text

    )

    return ApiResponse.success(data)


@router.post("/sessions/{session_no}/lecture/generate/stream", summary="流式生成沉浸式讲解（分步进度）")
async def stream_generate_immersive_lecture(
    session_no: str,
    req: TutorLectureGenerateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    service = TutorService(db)

    async def event_stream():
        async for event_type, payload in service.stream_generate_immersive_lecture(
            current_user, session_no, req.topic, req.source_text
        ):
            yield f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers=SSE_HEADERS,
    )


@router.get("/sessions/{session_no}/lecture/{lecture_id}", summary="获取讲解详情")

def get_immersive_lecture(

    session_no: str,

    lecture_id: str,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[dict]:

    return ApiResponse.success(TutorService(db).get_immersive_lecture(current_user, session_no, lecture_id))





@router.get("/sessions/{session_no}/lecture/{lecture_id}/export", summary="导出 PPTX")

def export_lecture_pptx(

    session_no: str,

    lecture_id: str,

    current_user: CurrentUser,

    db: DbSession,

):

    data, filename = TutorService(db).export_lecture_pptx(current_user, session_no, lecture_id)

    try:
        filename.encode("ascii")
        disposition = f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        ascii_name = "lecture.pptx"
        encoded = quote(filename, safe="")
        disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"

    return Response(

        content=data,

        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",

        headers={"Content-Disposition": disposition},

    )





@router.post("/sessions/{session_no}/lecture/{lecture_id}/ask", summary="侧边栏提问")

async def lecture_side_ask(

    session_no: str,

    lecture_id: str,

    req: TutorLectureSideAskRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[dict]:

    answer = await TutorService(db).lecture_side_ask(

        current_user, session_no, lecture_id, req.question, req.slide_index, req.history

    )

    return ApiResponse.success({"answer": answer})





@router.post("/sessions/{session_no}/lecture/{lecture_id}/quiz", summary="提交随堂测验")

def submit_lecture_quiz(

    session_no: str,

    lecture_id: str,

    req: TutorLectureQuizSubmitRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[dict]:

    result = TutorService(db).submit_lecture_quiz(

        current_user, session_no, lecture_id, req.slide_index, req.answers

    )

    return ApiResponse.success(result)





@router.get(

    "/sessions/{session_no}/lecture/{lecture_id}/summary",

    summary="讲解完成总结",

    response_model=ApiResponse[TutorLectureSummary],

)

def get_lecture_summary(

    session_no: str,

    lecture_id: str,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorLectureSummary]:

    data = TutorService(db).get_lecture_summary(current_user, session_no, lecture_id)

    return ApiResponse.success(TutorLectureSummary(**data))





@router.post(

    "/sessions/{session_no}/multimodal",

    summary="多模态生成（图像/视频/TTS）",

    response_model=ApiResponse[TutorMultimodalResponse],

)

async def multimodal_generate(

    session_no: str,

    req: TutorMultimodalRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorMultimodalResponse]:

    payload = await TutorService(db).generate_multimodal(

        current_user, session_no, req.action, req.prompt, req.source_text

    )

    return ApiResponse.success(TutorMultimodalResponse(action=req.action, payload=payload))





@router.post(

    "/sessions/{session_no}/message",

    summary="发送消息（非流式）",

    response_model=ApiResponse[TutorMessageResponse],

)

async def send_message(

    session_no: str,

    req: TutorMessageRequest,

    current_user: CurrentUser,

    db: DbSession,

) -> ApiResponse[TutorMessageResponse]:

    data = await TutorService(db).send_message(current_user, session_no, req)

    return ApiResponse.success(data)





@router.post("/sessions/{session_no}/message/stream", summary="发送消息（SSE流式）")

async def stream_message(

    session_no: str,

    req: TutorMessageRequest,

    current_user: CurrentUser,

    db: DbSession,

):

    service = TutorService(db)



    async def event_stream():

        async for event_type, payload in service.stream_message(current_user, session_no, req):

            yield f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"



    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers=SSE_HEADERS,
    )

