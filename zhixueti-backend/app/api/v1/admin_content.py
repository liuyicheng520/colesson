"""Admin content management API — Phase 2."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.deps import CurrentAdmin, DbSession
from app.core.response import ApiResponse
from app.schemas.admin_content import (
    AdminDocumentAuditRequest,
    AdminDocumentBatchAuditRequest,
    AdminDocumentListItem,
    AdminDocumentPreviewResponse,
    AdminDocumentSettingsRequest,
    AdminDocumentSettingsResponse,
    AdminImageListItem,
    AdminImagePreviewResponse,
    AdminKnowledgePointCreateRequest,
    AdminKnowledgePointItem,
    AdminKnowledgePointUpdateRequest,
    AdminLectureListItem,
    AdminLecturePreviewResponse,
    AdminPathDetailResponse,
    AdminPathListItem,
    AdminProfileDimensionCreateRequest,
    AdminProfileDimensionItem,
    AdminProfileDimensionUpdateRequest,
    AdminProfileTagItem,
    AdminProfileTagUpsertRequest,
    AdminResourceBatchStatusRequest,
    AdminResourceListResponse,
    AdminResourcePreviewResponse,
    AdminResourceStatusRequest,
)
from app.services.admin_content_service import (
    AdminDocumentService,
    AdminGeneratedContentService,
    AdminPathService,
    AdminProfileConfigService,
    AdminResourceService,
)

router = APIRouter()


class PageResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


# ── Resources ──────────────────────────────────────────────────────────────


@router.get("/resources", summary="全站资源列表", response_model=ApiResponse[AdminResourceListResponse])
def admin_list_resources(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    type_code: str | None = Query(None),
    status: int | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[AdminResourceListResponse]:
    data = AdminResourceService(db).list_resources(
        current_user.id,
        keyword=keyword,
        type_code=type_code,
        status=status,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(data)


@router.put("/resources/{resource_id}/status", summary="更新资源状态（发布/下架/拒绝）")
def admin_set_resource_status(
    resource_id: int,
    req: AdminResourceStatusRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    AdminResourceService(db).set_status(current_user.id, resource_id, req.status)
    return ApiResponse.success({"id": resource_id, "status": req.status})


@router.post("/resources/batch-status", summary="批量更新资源状态")
def admin_batch_resource_status(
    req: AdminResourceBatchStatusRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    count = AdminResourceService(db).batch_status(current_user.id, req.ids, req.status)
    return ApiResponse.success({"updated": count, "status": req.status})


@router.delete("/resources/{resource_id}", summary="删除资源（软删）")
def admin_delete_resource(
    resource_id: int, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[dict]:
    AdminResourceService(db).delete(current_user.id, resource_id)
    return ApiResponse.success({"id": resource_id, "deleted": True})


@router.get("/resources/export", summary="导出资源 JSON")
def admin_export_resources(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list]:
    data = AdminResourceService(db).export_json(current_user.id)
    return ApiResponse.success(data)


@router.get("/resources/{resource_id}/preview", summary="预览资源内容")
def admin_resource_preview(
    resource_id: int, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminResourcePreviewResponse]:
    return ApiResponse.success(AdminResourceService(db).get_preview(current_user.id, resource_id))


# ── Profile config ───────────────────────────────────────────────────────────


@router.get("/profile/dimensions", summary="画像维度列表", response_model=ApiResponse[list[AdminProfileDimensionItem]])
def admin_list_dimensions(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[AdminProfileDimensionItem]]:
    return ApiResponse.success(AdminProfileConfigService(db).list_dimensions(current_user.id))


@router.post("/profile/dimensions", summary="新增画像维度", response_model=ApiResponse[AdminProfileDimensionItem])
def admin_create_dimension(
    req: AdminProfileDimensionCreateRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminProfileDimensionItem]:
    return ApiResponse.success(AdminProfileConfigService(db).create_dimension(current_user.id, req))


@router.put("/profile/dimensions/{dim_id}", summary="编辑画像维度", response_model=ApiResponse[AdminProfileDimensionItem])
def admin_update_dimension(
    dim_id: int,
    req: AdminProfileDimensionUpdateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[AdminProfileDimensionItem]:
    return ApiResponse.success(AdminProfileConfigService(db).update_dimension(current_user.id, dim_id, req))


@router.delete("/profile/dimensions/{dim_id}", summary="禁用画像维度")
def admin_delete_dimension(dim_id: int, current_user: CurrentAdmin, db: DbSession) -> ApiResponse[dict]:
    AdminProfileConfigService(db).delete_dimension(current_user.id, dim_id)
    return ApiResponse.success({"id": dim_id, "disabled": True})


@router.get("/profile/tags", summary="画像标签库", response_model=ApiResponse[list[AdminProfileTagItem]])
def admin_list_tags(current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[AdminProfileTagItem]]:
    return ApiResponse.success(AdminProfileConfigService(db).list_tags(current_user.id))


@router.post("/profile/tags", summary="新增/更新标签", response_model=ApiResponse[list[AdminProfileTagItem]])
def admin_upsert_tag(
    req: AdminProfileTagUpsertRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[list[AdminProfileTagItem]]:
    return ApiResponse.success(AdminProfileConfigService(db).upsert_tag(current_user.id, req))


@router.delete("/profile/tags/{code}", summary="删除标签", response_model=ApiResponse[list[AdminProfileTagItem]])
def admin_delete_tag(code: str, current_user: CurrentAdmin, db: DbSession) -> ApiResponse[list[AdminProfileTagItem]]:
    return ApiResponse.success(AdminProfileConfigService(db).delete_tag(current_user.id, code))


# ── Learning paths ───────────────────────────────────────────────────────────


@router.get("/paths", summary="学习路径列表")
def admin_list_paths(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageResponse]:
    items, total = AdminPathService(db).list_paths(
        current_user.id, keyword=keyword, user_id=user_id, page=page, page_size=page_size
    )
    return ApiResponse.success(PageResponse(items=items, total=total, page=page, page_size=page_size))


@router.get("/paths/{path_id}", summary="学习路径详情", response_model=ApiResponse[AdminPathDetailResponse])
def admin_get_path(path_id: int, current_user: CurrentAdmin, db: DbSession) -> ApiResponse[AdminPathDetailResponse]:
    return ApiResponse.success(AdminPathService(db).get_path_detail(current_user.id, path_id))


@router.get("/knowledge-points", summary="知识点列表", response_model=ApiResponse[list[AdminKnowledgePointItem]])
def admin_list_knowledge_points(
    current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[list[AdminKnowledgePointItem]]:
    return ApiResponse.success(AdminPathService(db).list_knowledge_points(current_user.id))


@router.post("/knowledge-points", summary="新增知识点", response_model=ApiResponse[AdminKnowledgePointItem])
def admin_create_knowledge_point(
    req: AdminKnowledgePointCreateRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminKnowledgePointItem]:
    return ApiResponse.success(AdminPathService(db).create_knowledge_point(current_user.id, req))


@router.put("/knowledge-points/{point_id}", summary="编辑知识点", response_model=ApiResponse[AdminKnowledgePointItem])
def admin_update_knowledge_point(
    point_id: int,
    req: AdminKnowledgePointUpdateRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[AdminKnowledgePointItem]:
    return ApiResponse.success(AdminPathService(db).update_knowledge_point(current_user.id, point_id, req))


@router.delete("/knowledge-points/{point_id}", summary="禁用知识点")
def admin_delete_knowledge_point(point_id: int, current_user: CurrentAdmin, db: DbSession) -> ApiResponse[dict]:
    AdminPathService(db).delete_knowledge_point(current_user.id, point_id)
    return ApiResponse.success({"id": point_id, "disabled": True})


# ── Generated content ────────────────────────────────────────────────────────


@router.get("/generated/lectures", summary="视频讲解内容列表")
def admin_list_lectures(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageResponse]:
    items, total = AdminGeneratedContentService(db).list_lectures(
        current_user.id, keyword=keyword, user_id=user_id, page=page, page_size=page_size
    )
    return ApiResponse.success(PageResponse(items=items, total=total, page=page, page_size=page_size))


@router.delete("/generated/lectures/{session_id}/{lecture_id}", summary="删除讲解内容")
def admin_delete_lecture(
    session_id: int, lecture_id: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[dict]:
    AdminGeneratedContentService(db).delete_lecture(current_user.id, session_id, lecture_id)
    return ApiResponse.success({"session_id": session_id, "lecture_id": lecture_id, "deleted": True})


@router.get("/generated/lectures/{session_id}/{lecture_id}/preview", summary="预览讲解内容")
def admin_lecture_preview(
    session_id: int, lecture_id: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminLecturePreviewResponse]:
    return ApiResponse.success(
        AdminGeneratedContentService(db).get_lecture_preview(current_user.id, session_id, lecture_id)
    )


@router.get("/generated/images", summary="图像生成内容列表")
def admin_list_images(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageResponse]:
    items, total = AdminGeneratedContentService(db).list_images(
        current_user.id, keyword=keyword, user_id=user_id, page=page, page_size=page_size
    )
    return ApiResponse.success(PageResponse(items=items, total=total, page=page, page_size=page_size))


@router.delete("/generated/images/{session_id}/{round_no}", summary="删除图像生成内容")
def admin_delete_image(
    session_id: int, round_no: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[dict]:
    AdminGeneratedContentService(db).delete_image(current_user.id, session_id, round_no)
    return ApiResponse.success({"session_id": session_id, "round_no": round_no, "deleted": True})


@router.get("/generated/images/{session_id}/{round_no}/preview", summary="预览图像内容")
def admin_image_preview(
    session_id: int, round_no: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminImagePreviewResponse]:
    return ApiResponse.success(
        AdminGeneratedContentService(db).get_image_preview(current_user.id, session_id, round_no)
    )


# ── Documents ────────────────────────────────────────────────────────────────


@router.get("/documents", summary="用户上传文档列表")
def admin_list_documents(
    current_user: CurrentAdmin,
    db: DbSession,
    keyword: str | None = Query(None),
    audit_status: int | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PageResponse]:
    items, total = AdminDocumentService(db).list_documents(
        current_user.id,
        keyword=keyword,
        audit_status=audit_status,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.success(PageResponse(items=items, total=total, page=page, page_size=page_size))


@router.get("/documents/settings", summary="文档审核配置", response_model=ApiResponse[AdminDocumentSettingsResponse])
def admin_get_document_settings(
    current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminDocumentSettingsResponse]:
    return ApiResponse.success(AdminDocumentService(db).get_settings(current_user.id))


@router.put("/documents/settings", summary="更新文档审核配置", response_model=ApiResponse[AdminDocumentSettingsResponse])
def admin_update_document_settings(
    req: AdminDocumentSettingsRequest, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminDocumentSettingsResponse]:
    return ApiResponse.success(AdminDocumentService(db).update_settings(current_user.id, req))


@router.put("/documents/{user_id}/{doc_id}/audit", summary="审核用户文档")
def admin_audit_document(
    user_id: int,
    doc_id: str,
    req: AdminDocumentAuditRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    AdminDocumentService(db).audit_document(
        current_user.id, user_id, doc_id, req.audit_status, req.reason
    )
    return ApiResponse.success({"doc_id": doc_id, "audit_status": req.audit_status})


@router.post("/documents/batch-audit", summary="批量审核用户文档")
def admin_batch_audit_documents(
    req: AdminDocumentBatchAuditRequest,
    current_user: CurrentAdmin,
    db: DbSession,
) -> ApiResponse[dict]:
    count = AdminDocumentService(db).batch_audit_documents(
        current_user.id, req.items, req.audit_status, req.reason
    )
    return ApiResponse.success({"updated": count, "audit_status": req.audit_status})


@router.delete("/documents/{user_id}/{doc_id}", summary="删除用户文档")
def admin_delete_document(
    user_id: int, doc_id: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[dict]:
    AdminDocumentService(db).delete_document(current_user.id, user_id, doc_id)
    return ApiResponse.success({"doc_id": doc_id, "deleted": True})


@router.get("/documents/{user_id}/{doc_id}/preview", summary="预览用户文档内容")
def admin_document_preview(
    user_id: int, doc_id: str, current_user: CurrentAdmin, db: DbSession
) -> ApiResponse[AdminDocumentPreviewResponse]:
    return ApiResponse.success(AdminDocumentService(db).get_document_preview(current_user.id, user_id, doc_id))
