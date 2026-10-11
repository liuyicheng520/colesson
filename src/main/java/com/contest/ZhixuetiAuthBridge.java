package com.contest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.HttpURLConnection;
import java.net.URI;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 学生开通/登录成功后，向内部学生服务领取 JWT。
 * 对外仍只走 8082；此处访问本机内部端口，对用户呈现为同一套智课共生账号。
 */
@Component
public class ZhixuetiAuthBridge {

    private static final Logger log = LoggerFactory.getLogger(ZhixuetiAuthBridge.class);
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    private final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(12, TimeUnit.SECONDS)
            .writeTimeout(12, TimeUnit.SECONDS)
            .callTimeout(15, TimeUnit.SECONDS)
            .build();

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${zhixueti.backend-base:http://127.0.0.1:8000}")
    private String backendBase;

    /** 与 HTTP 反代解耦：默认开启，不随 ZHIXUETI_PROXY_ENABLED=false 一起关掉。 */
    @Value("${zhixueti.auth-bridge-enabled:true}")
    private boolean enabled;

    /** 与学生端约定共享的桥接密钥：学生端 /auth/sync-student 校验 X-Host-Secret 头。 */
    @Value("${zhixueti.bridge-secret:}")
    private String bridgeSecret;

    /**
     * 单一账号体系：宿主登录成功后，把账号（含真实身份）同步到学生/管理服务并领取 JWT。
     * userType: 1=学生 2=教师 3=管理员
     */
    public Map<String, Object> ensureAccountTokens(String username, String password, int userType) {
        if (!enabled || username == null || username.trim().isEmpty() || password == null) {
            return null;
        }
        if (!waitUntilHealthy(4)) {
            log.warn("智学体服务尚未就绪，无法完成账号同步：{}", trimTrailingSlash(backendBase));
            return null;
        }
        for (int attempt = 1; attempt <= 4; attempt++) {
            Map<String, Object> tokens = postForTokens(
                    "/api/v1/auth/sync-account", username, password, false, userType);
            if (tokens != null) {
                return tokens;
            }
            log.warn("账号同步未成功，第 {} 次重试：{}", attempt, username.trim());
            sleepQuietly(700L * attempt);
        }
        return null;
    }

    public Map<String, Object> ensureStudentTokens(String username, String password) {
        if (!enabled || username == null || username.trim().isEmpty() || password == null) {
            return null;
        }
        // 健康检查最多等约 4 秒，避免登录接口长时间阻塞打卡整站
        if (!waitUntilHealthy(4)) {
            log.warn("学生服务尚未就绪，无法完成账号凭证签发：{}", trimTrailingSlash(backendBase));
            return null;
        }

        // 同一套账号：同步密码并签发学生端 JWT（最多重试几次，避免启动瞬时失败）
        for (int attempt = 1; attempt <= 4; attempt++) {
            Map<String, Object> tokens = postForTokens("/api/v1/auth/sync-student", username, password);
            if (tokens != null) {
                return tokens;
            }
            tokens = postForTokens("/api/v1/auth/login", username, password);
            if (tokens != null) {
                return tokens;
            }
            postForTokens("/api/v1/auth/register", username, password, true);
            tokens = postForTokens("/api/v1/auth/login", username, password);
            if (tokens != null) {
                return tokens;
            }
            log.warn("学生凭证签发未成功，第 {} 次重试：{}", attempt, username.trim());
            sleepQuietly(700L * attempt);
        }
        return null;
    }

    private Map<String, Object> postForTokens(String path, String username, String password) {
        return postForTokens(path, username, password, false, 1);
    }

    private Map<String, Object> postForTokens(String path, String username, String password, boolean asRegister) {
        return postForTokens(path, username, password, asRegister, 1);
    }

    private Map<String, Object> postForTokens(String path, String username, String password,
                                              boolean asRegister, int userType) {
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("username", username.trim());
            body.put("password", password);
            body.put("user_type", userType);
            if (asRegister) {
                body.put("nickname", username.trim());
            }
            String url = trimTrailingSlash(backendBase) + path;
            Request.Builder builder = new Request.Builder()
                    .url(url)
                    .post(RequestBody.create(objectMapper.writeValueAsBytes(body), JSON))
                    .header("Content-Type", "application/json; charset=utf-8");
            if (bridgeSecret != null && !bridgeSecret.trim().isEmpty()) {
                builder.header("X-Host-Secret", bridgeSecret.trim());
            }
            Request request = builder.build();
            try (Response response = client.newCall(request).execute()) {
                if (response.body() == null) {
                    return null;
                }
                String raw = response.body().string();
                JsonNode root = objectMapper.readTree(raw);
                if (root.path("code").asInt(-1) != 0) {
                    return null;
                }
                JsonNode data = root.path("data");
                if (data.isMissingNode() || !data.hasNonNull("access_token")) {
                    return null;
                }
                Map<String, Object> tokens = new HashMap<>();
                tokens.put("access_token", data.path("access_token").asText());
                if (data.hasNonNull("refresh_token")) {
                    tokens.put("refresh_token", data.path("refresh_token").asText());
                }
                return tokens;
            }
        } catch (Exception ex) {
            log.debug("学生服务请求失败 {}: {}", path, ex.getMessage());
            return null;
        }
    }

    private boolean waitUntilHealthy(int seconds) {
        long deadline = System.currentTimeMillis() + seconds * 1000L;
        while (System.currentTimeMillis() < deadline) {
            if (isHealthy()) {
                return true;
            }
            sleepQuietly(500);
        }
        return isHealthy();
    }

    private boolean isHealthy() {
        HttpURLConnection conn = null;
        try {
            URI uri = URI.create(trimTrailingSlash(backendBase) + "/health");
            conn = (HttpURLConnection) uri.toURL().openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(2000);
            conn.setRequestMethod("GET");
            int code = conn.getResponseCode();
            return code >= 200 && code < 500;
        } catch (Exception ex) {
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static String trimTrailingSlash(String value) {
        if (value == null || value.isEmpty()) {
            return "http://127.0.0.1:8000";
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
