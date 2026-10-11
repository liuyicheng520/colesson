package com.contest;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@RestController
public class AuthController {

    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";

    /** 登录/注册接口固定窗口频控（按 IP）：防爆破与批量注册 */
    private static final long AUTH_RATE_WINDOW_MS = 60_000L;
    private static final int AUTH_RATE_LIMIT = 10;
    private final ConcurrentHashMap<String, long[]> authRateCounters = new ConcurrentHashMap<>();

    private boolean authRateLimited(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        String ip = (xff == null || xff.isBlank()) ? request.getRemoteAddr() : xff.split(",")[0].trim();
        long now = System.currentTimeMillis();
        long[] slot = authRateCounters.compute(ip, (k, v) -> {
            if (v == null || now - v[0] >= AUTH_RATE_WINDOW_MS) {
                return new long[]{now, 1};
            }
            v[1]++;
            return v;
        });
        if (authRateCounters.size() > 5_000) {
            authRateCounters.entrySet().removeIf(e -> now - e.getValue()[0] >= AUTH_RATE_WINDOW_MS);
        }
        return slot[1] > AUTH_RATE_LIMIT;
    }

    private final AuthService authService;
    private final ZhixuetiAuthBridge zhixuetiAuthBridge;

    public AuthController(AuthService authService, ZhixuetiAuthBridge zhixuetiAuthBridge) {
        this.authService = authService;
        this.zhixuetiAuthBridge = zhixuetiAuthBridge;
    }

    @PostMapping("/auth/register")
    public ResponseEntity<ApiResponse<Map<String, Object>>> register(
            @RequestBody Map<String, String> request,
            HttpServletRequest servletRequest
    ) {
        if (authRateLimited(servletRequest)) {
            return ResponseEntity.status(429).body(ApiResponse.error("操作过于频繁，请稍后再试"));
        }
        String username = request.get("username");
        String password = request.get("password");
        return handleAuthSuccess(
                authService.register(username, password, request.get("role")),
                "注册成功",
                username,
                password
        );
    }

    @PostMapping("/auth/login")
    public ResponseEntity<ApiResponse<Map<String, Object>>> login(
            @RequestBody Map<String, String> request,
            HttpServletRequest servletRequest
    ) {
        if (authRateLimited(servletRequest)) {
            return ResponseEntity.status(429).body(ApiResponse.error("操作过于频繁，请稍后再试"));
        }
        String username = request.get("username");
        String password = request.get("password");
        return handleAuthSuccess(
                authService.login(username, password, request.get("entryRole")),
                "登录成功",
                username,
                password
        );
    }

    @PostMapping("/auth/logout")
    public ResponseEntity<ApiResponse<Map<String, Object>>> logout(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        authService.logout(sessionId);
        ResponseCookie cookie = ResponseCookie.from(AUTH_COOKIE, "")
                .httpOnly(true)
                .path("/")
                .sameSite("Lax")
                .maxAge(Duration.ZERO)
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookie.toString())
                .body(ApiResponse.success("已退出登录", new HashMap<>()));
    }

    @GetMapping("/auth/me")
    public ResponseEntity<ApiResponse<Map<String, Object>>> me(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = authService.getUserBySession(sessionId);
        if (user == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error("未登录"));
        }
        Map<String, Object> data = new HashMap<>();
        data.put("user", user);
        return ResponseEntity.ok(ApiResponse.success("获取当前用户成功", data));
    }

    @PostMapping("/auth/change-password")
    public ResponseEntity<ApiResponse<Map<String, Object>>> changePassword(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, String> request
    ) {
        authService.changePassword(sessionId, request.get("oldPassword"), request.get("newPassword"));
        return ResponseEntity.ok(ApiResponse.success("密码修改成功", new HashMap<>()));
    }

    @PostMapping("/auth/password-reset-request")
    public ResponseEntity<ApiResponse<Map<String, Object>>> passwordResetRequest(@RequestBody Map<String, String> request) {
        AuthService.PasswordResetRequest item = authService.submitPasswordResetRequest(
                request.get("username"),
                request.get("roleHint"),
                request.get("reason"),
                request.get("contact")
        );
        Map<String, Object> data = new HashMap<>();
        data.put("requestId", item.getId());
        data.put("status", item.getStatus());
        return ResponseEntity.ok(ApiResponse.success("重置申请已提交，请等待管理员处理", data));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> handleAuthSuccess(
            AuthService.AuthResult result,
            String message,
            String username,
            String password
    ) {
        ResponseCookie cookie = ResponseCookie.from(AUTH_COOKIE, result.getSessionId())
                .httpOnly(true)
                .path("/")
                .sameSite("Lax")
                .maxAge(Duration.ofHours(12))
                .build();

        Map<String, Object> data = new HashMap<>();
        data.put("user", result.getUser());

        AuthService.AuthUserView user = result.getUser();
        if (user != null) {
            // 单一账号体系：任何角色登录都以宿主身份为准同步到学生/管理服务
            // （管理员=3、教师=2、学生=1），避免两侧账号或身份不一致。
            int userType = user.hasActiveRole("admin") ? 3 : (user.hasActiveRole("teacher") ? 2 : 1);
            Map<String, Object> zhixueti = zhixuetiAuthBridge.ensureAccountTokens(username, password, userType);
            if (zhixueti != null && !zhixueti.isEmpty()) {
                data.put("zhixueti", zhixueti);
            }
        }

        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookie.toString())
                .body(ApiResponse.success(message, data));
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(AuthService.AuthException.class)
    public ResponseEntity<ApiResponse<Map<String, Object>>> handleAuthException(AuthService.AuthException ex) {
        return ResponseEntity.badRequest().body(ApiResponse.error(ex.getMessage()));
    }
}
