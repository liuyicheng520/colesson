"""Unified business error codes."""

from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0

    # Auth 1xxx
    AUTH_INVALID_CREDENTIALS = 1001
    AUTH_TOKEN_EXPIRED = 1002
    AUTH_TOKEN_INVALID = 1003
    AUTH_PERMISSION_DENIED = 1004
    AUTH_USER_DISABLED = 1005
    AUTH_USER_EXISTS = 1006

    # Validation 2xxx
    VALIDATION_ERROR = 2001
    PARAM_MISSING = 2002
    PARAM_INVALID = 2003

    # Resource 3xxx
    NOT_FOUND = 3001
    USER_NOT_FOUND = 3002
    PROFILE_NOT_FOUND = 3003
    RESOURCE_NOT_FOUND = 3004
    PATH_NOT_FOUND = 3005
    TASK_NOT_FOUND = 3006
    AGENT_NOT_FOUND = 3007

    # Business 4xxx
    PROFILE_INCOMPLETE = 4001
    RESOURCE_AUDIT_REJECTED = 4002
    TASK_ALREADY_RUNNING = 4003
    TASK_CANCEL_FAILED = 4004
    PATH_NODE_LOCKED = 4005
    CONTENT_UNSAFE = 4006

    # LLM 5xxx
    LLM_PROVIDER_ERROR = 5001
    LLM_RATE_LIMITED = 5002
    LLM_CONTENT_FILTERED = 5003

    # System 9xxx
    INTERNAL_ERROR = 9001
    DATABASE_ERROR = 9002
    REDIS_ERROR = 9003
    RATE_LIMIT_EXCEEDED = 9004


ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.AUTH_INVALID_CREDENTIALS: "用户名或密码错误",
    ErrorCode.AUTH_TOKEN_EXPIRED: "Token已过期",
    ErrorCode.AUTH_TOKEN_INVALID: "Token无效",
    ErrorCode.AUTH_PERMISSION_DENIED: "权限不足",
    ErrorCode.AUTH_USER_DISABLED: "用户已被禁用",
    ErrorCode.AUTH_USER_EXISTS: "用户已存在",
    ErrorCode.VALIDATION_ERROR: "参数校验失败",
    ErrorCode.PARAM_MISSING: "缺少必要参数",
    ErrorCode.PARAM_INVALID: "参数格式无效",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.USER_NOT_FOUND: "用户不存在",
    ErrorCode.PROFILE_NOT_FOUND: "用户画像不存在",
    ErrorCode.RESOURCE_NOT_FOUND: "学习资源不存在",
    ErrorCode.PATH_NOT_FOUND: "学习路径不存在",
    ErrorCode.TASK_NOT_FOUND: "任务不存在",
    ErrorCode.AGENT_NOT_FOUND: "智能体不存在",
    ErrorCode.PROFILE_INCOMPLETE: "用户画像完整度不足",
    ErrorCode.RESOURCE_AUDIT_REJECTED: "资源未通过内容审核",
    ErrorCode.TASK_ALREADY_RUNNING: "任务已在执行中",
    ErrorCode.TASK_CANCEL_FAILED: "任务取消失败",
    ErrorCode.PATH_NODE_LOCKED: "路径节点尚未解锁",
    ErrorCode.CONTENT_UNSAFE: "内容未通过安全审核",
    ErrorCode.LLM_PROVIDER_ERROR: "大模型服务调用失败",
    ErrorCode.LLM_RATE_LIMITED: "大模型调用频率受限",
    ErrorCode.LLM_CONTENT_FILTERED: "内容被安全策略拦截",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    ErrorCode.DATABASE_ERROR: "数据库错误",
    ErrorCode.REDIS_ERROR: "缓存服务错误",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
}
