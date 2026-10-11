package com.contest;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * 将智学体 FastAPI 前缀同域反代到内部 :8000，浏览器只访问 8082。
 * 不代理宿主自有 /api/v1/lesson|qa|progress|platform。
 */
@Component
@Order(20)
public class ZhixuetiProxyFilter extends OncePerRequestFilter {

    private static final Set<String> HOP_BY_HOP = new HashSet<>(Arrays.asList(
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host"
    ));

    private static final String[] API_PREFIXES = {
            "/api/v1/auth/",
            "/api/v1/users/",
            "/api/v1/admin/",
            "/api/v1/system/",
            "/api/v1/security/",
            "/api/v1/profiles/",
            "/api/v1/behavior/",
            "/api/v1/resources/",
            "/api/v1/paths/",
            "/api/v1/tutor/",
            "/api/v1/agents/",
            "/api/v1/kb/",
            "/api/v1/llm/"
    };

    // 禁止无限超时：上游挂起时会占满 Tomcat 工作线程，导致整站假死变卡。
    // SSE/长生成最多等 5 分钟；普通 API 更快失败返回。
    private final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(300, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .callTimeout(310, TimeUnit.SECONDS)
            .build();

    @Value("${zhixueti.backend-base:http://127.0.0.1:8000}")
    private String backendBase;

    @Value("${zhixueti.proxy-enabled:true}")
    private boolean proxyEnabled;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (!proxyEnabled) {
            return true;
        }
        String path = request.getRequestURI();
        if (path == null) {
            return true;
        }
        if (path.startsWith("/uploads/") || path.equals("/uploads")) {
            return false;
        }
        for (String prefix : API_PREFIXES) {
            if (path.startsWith(prefix) || path.equals(prefix.substring(0, prefix.length() - 1))) {
                return false;
            }
        }
        return true;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        String query = request.getQueryString();
        String target = trimTrailingSlash(backendBase) + path + (query == null || query.isEmpty() ? "" : "?" + query);

        Request.Builder builder = new Request.Builder().url(target);
        Enumeration<String> headerNames = request.getHeaderNames();
        if (headerNames != null) {
            for (String name : Collections.list(headerNames)) {
                if (name == null) continue;
                String lower = name.toLowerCase(Locale.ROOT);
                if (HOP_BY_HOP.contains(lower)) continue;
                Enumeration<String> values = request.getHeaders(name);
                while (values.hasMoreElements()) {
                    builder.addHeader(name, values.nextElement());
                }
            }
        }

        String method = request.getMethod() == null ? "GET" : request.getMethod().toUpperCase(Locale.ROOT);
        RequestBody body = null;
        if (!"GET".equals(method) && !"HEAD".equals(method) && !"DELETE".equals(method)) {
            byte[] bytes = request.getInputStream().readAllBytes();
            String contentType = request.getContentType();
            MediaType mediaType = contentType == null ? null : MediaType.parse(contentType);
            body = RequestBody.create(bytes, mediaType);
        } else if ("DELETE".equals(method) && request.getContentLengthLong() > 0) {
            byte[] bytes = request.getInputStream().readAllBytes();
            String contentType = request.getContentType();
            MediaType mediaType = contentType == null ? null : MediaType.parse(contentType);
            body = RequestBody.create(bytes, mediaType);
        }

        builder.method(method, body);

        try (Response upstream = client.newCall(builder.build()).execute()) {
            response.setStatus(upstream.code());
            for (String name : upstream.headers().names()) {
                String lower = name.toLowerCase(Locale.ROOT);
                if (HOP_BY_HOP.contains(lower)) continue;
                for (String value : upstream.headers(name)) {
                    response.addHeader(name, value);
                }
            }
            ResponseBody upstreamBody = upstream.body();
            if (upstreamBody == null) {
                return;
            }
            try (InputStream in = upstreamBody.byteStream(); OutputStream out = response.getOutputStream()) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    out.write(buf, 0, n);
                    out.flush();
                }
            }
        } catch (IOException ex) {
            if (!response.isCommitted()) {
                response.resetBuffer();
                response.setStatus(HttpServletResponse.SC_BAD_GATEWAY);
                response.setContentType("application/json;charset=UTF-8");
                response.getWriter().write("{\"code\":502,\"message\":\"智学体后端不可用，请确认内部 FastAPI(8000) 已启动\",\"data\":null}");
            }
        }
    }

    private static String trimTrailingSlash(String base) {
        if (base == null || base.isEmpty()) {
            return "http://127.0.0.1:8000";
        }
        return base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
    }
}
