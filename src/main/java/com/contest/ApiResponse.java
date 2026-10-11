package com.contest;

public class ApiResponse<T> {
    private int code;
    private String message;
    private String msg;
    private T data;
    private String requestId;

    public ApiResponse() {
    }

    public ApiResponse(int code, String message, T data, String requestId) {
        this.code = code;
        this.message = message;
        this.msg = message;
        this.data = data;
        this.requestId = requestId;
    }

    public static <T> ApiResponse<T> success(String message, T data) {
        return new ApiResponse<>(0, message, data, null);
    }

    public static <T> ApiResponse<T> success(String message, T data, String requestId) {
        return new ApiResponse<>(0, message, data, requestId);
    }

    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(1, message, null, null);
    }

    public static <T> ApiResponse<T> error(String message, String requestId) {
        return new ApiResponse<>(1, message, null, requestId);
    }

    public int getCode() {
        return code;
    }

    public void setCode(int code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
        this.msg = message;
    }

    public String getMsg() {
        return msg;
    }

    public void setMsg(String msg) {
        this.msg = msg;
        this.message = msg;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }
}
