package com.contest;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public class DigitalHumanCloudUtil {
    private static final MediaType JSON_TYPE = MediaType.parse("application/json; charset=utf-8");

    private DigitalHumanCloudUtil() {
    }

    public static Map<String, String> createVideo(
            String cloudUrl,
            String apiKey,
            String authHeader,
            String authPrefix,
            String ak,
            String sk,
            String region,
            String service,
            String reqKey,
            String resourceId,
            String audioUrl,
            int timeoutMs,
            int pollAttempts,
            int pollIntervalMs
    ) {
        return createVideoInternal(
                cloudUrl, apiKey, authHeader, authPrefix, ak, sk, region, service,
                reqKey, resourceId, audioUrl, timeoutMs, pollAttempts, pollIntervalMs
        );
    }

    private static Map<String, String> createVideoInternal(
            String cloudUrl,
            String apiKey,
            String authHeader,
            String authPrefix,
            String ak,
            String sk,
            String region,
            String service,
            String reqKey,
            String resourceId,
            String audioUrl,
            int timeoutMs,
            int pollAttempts,
            int pollIntervalMs
    ) {
        Map<String, String> result = new HashMap<>();
        result.put("success", "false");

        if (cloudUrl == null || cloudUrl.trim().isEmpty()) {
            result.put("error", "云端地址未配置");
            return result;
        }
        if (reqKey == null || reqKey.trim().isEmpty()) {
            result.put("error", "req_key 未配置");
            return result;
        }
        if (resourceId == null || resourceId.trim().isEmpty()) {
            result.put("error", "resource_id 未配置");
            return result;
        }

        int safeTimeout = Math.max(timeoutMs, 1000);
        OkHttpClient client = new OkHttpClient.Builder()
                .connectTimeout(safeTimeout, TimeUnit.MILLISECONDS)
                .readTimeout(safeTimeout, TimeUnit.MILLISECONDS)
                .writeTimeout(safeTimeout, TimeUnit.MILLISECONDS)
                .callTimeout(safeTimeout, TimeUnit.MILLISECONDS)
                .build();

        try {
            String submitUrl = appendQuery(cloudUrl, "Action=CVSubmitTask&Version=2022-08-31");
            JSONObject submitBody = new JSONObject();
            submitBody.put("req_key", reqKey);
            submitBody.put("resource_id", resourceId);
            submitBody.put("audio_url", audioUrl);

            String activeSk = sk;
            int requestAttempts = safeTimeout <= 2000 ? 1 : 2;
            JSONObject submitJson = null;
            List<String> skCandidates = buildSkCandidates(sk);
            if (hasText(ak) && !skCandidates.isEmpty()) {
                JSONObject lastSigError = null;
                for (String candidateSk : skCandidates) {
                    JSONObject tmp = postJsonWithRetry(client, submitUrl, submitBody, apiKey, authHeader, authPrefix, ak, candidateSk, region, service, requestAttempts);
                    if (isSignatureMismatch(tmp)) {
                        lastSigError = tmp;
                        continue;
                    }
                    submitJson = tmp;
                    activeSk = candidateSk;
                    break;
                }
                if (submitJson == null) {
                    submitJson = lastSigError;
                }
            } else {
                submitJson = postJsonWithRetry(client, submitUrl, submitBody, apiKey, authHeader, authPrefix, ak, sk, region, service, requestAttempts);
            }
            if (submitJson == null) {
                result.put("error", "提交任务失败：响应为空");
                return result;
            }
            if (submitJson.containsKey("code")) {
                String code = extractStr(submitJson, "code");
                if (!"10000".equals(code)) {
                    String msg = extractStr(submitJson, "message");
                    result.put("error", "提交任务失败，code=" + code + " message=" + msg);
                    return result;
                }
            }

            String taskId = extractStr(submitJson, "task_id");
            if (taskId.isEmpty() && submitJson.containsKey("data")) {
                taskId = extractStr(submitJson.getJSONObject("data"), "task_id");
            }
            if (taskId.isEmpty()) {
                result.put("error", "提交任务成功但未返回 task_id");
                return result;
            }
            result.put("taskId", taskId);

            String queryUrl = appendQuery(cloudUrl, "Action=CVGetResult&Version=2022-08-31");
            int attempts = Math.max(pollAttempts, 1);
            int interval = Math.max(pollIntervalMs, 200);
            for (int i = 0; i < attempts; i++) {
                JSONObject queryBody = new JSONObject();
                queryBody.put("req_key", reqKey);
                queryBody.put("task_id", taskId);

                JSONObject queryJson = postJsonWithRetry(client, queryUrl, queryBody, apiKey, authHeader, authPrefix, ak, activeSk, region, service, requestAttempts);
                if (queryJson != null) {
                    if (queryJson.containsKey("code")) {
                        String code = extractStr(queryJson, "code");
                        if (!code.isEmpty() && !"10000".equals(code)) {
                            result.put("error", "查询任务失败，code=" + code + " message=" + extractStr(queryJson, "message"));
                            return result;
                        }
                    }
                    String videoUrl = extractVideoUrl(queryJson);
                    if (!videoUrl.isEmpty()) {
                        result.put("success", "true");
                        result.put("videoUrl", videoUrl);
                        return result;
                    }
                }
                if (i < attempts - 1) {
                    Thread.sleep(interval);
                }
            }
            result.put("error", "轮询超时：未获取到 video_url");
            return result;
        } catch (IOException e) {
            result.put("error", "云端请求异常：" + e.getMessage());
            return result;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            result.put("error", "轮询被中断");
            return result;
        }
    }

    private static JSONObject postJson(
            OkHttpClient client,
            String url,
            JSONObject body,
            String apiKey,
            String authHeader,
            String authPrefix,
            String ak,
            String sk,
            String region,
            String service
    ) throws IOException {
        String requestBody = body.toString();

        if (hasText(ak) && hasText(sk)) {
            String r = defaultIfBlank(region, "cn-north-1");
            String s = defaultIfBlank(service, "cv");
            Request headerReq = buildHeaderSignedRequest(url, requestBody, ak.trim(), sk.trim(), r, s);
            JSONObject first = executeRequest(client, headerReq);
            if (!isSignatureMismatch(first)) {
                return first;
            }

            // 文档支持 Query 签名，这里做自动兜底重试
            Request queryReq = buildQuerySignedRequest(url, requestBody, ak.trim(), sk.trim(), r, s);
            return executeRequest(client, queryReq);
        }

        Request.Builder builder = new Request.Builder()
                .url(url)
                .addHeader("Content-Type", "application/json")
                .post(RequestBody.create(requestBody, JSON_TYPE));
        if (apiKey != null && !apiKey.trim().isEmpty()) {
            String header = (authHeader == null || authHeader.trim().isEmpty()) ? "Authorization" : authHeader.trim();
            String prefix = authPrefix == null ? "" : authPrefix.trim();
            String value = prefix.isEmpty() ? apiKey.trim() : (prefix + " " + apiKey.trim());
            builder.addHeader(header, value);
        }
        return executeRequest(client, builder.build());
    }

    private static JSONObject postJsonWithRetry(
            OkHttpClient client,
            String url,
            JSONObject body,
            String apiKey,
            String authHeader,
            String authPrefix,
            String ak,
            String sk,
            String region,
            String service,
            int attempts
    ) throws IOException {
        IOException last = null;
        int n = Math.max(attempts, 1);
        for (int i = 0; i < n; i++) {
            try {
                return postJson(client, url, body, apiKey, authHeader, authPrefix, ak, sk, region, service);
            } catch (IOException e) {
                last = e;
                String m = String.valueOf(e.getMessage()).toLowerCase();
                boolean timeout = m.contains("timeout") || m.contains("timed out");
                if (!timeout || i == n - 1) {
                    throw e;
                }
            }
        }
        throw last == null ? new IOException("unknown io error") : last;
    }

    private static JSONObject executeRequest(OkHttpClient client, Request request) throws IOException {
        try (Response response = client.newCall(request).execute()) {
            String bodyText = response.body() == null ? "" : response.body().string();
            if (!response.isSuccessful()) {
                JSONObject error = new JSONObject();
                error.put("code", String.valueOf(response.code()));
                error.put("message", bodyText.isEmpty() ? ("HTTP " + response.code()) : bodyText);
                return error;
            }
            if (bodyText.isEmpty()) {
                JSONObject error = new JSONObject();
                error.put("code", "EMPTY_BODY");
                error.put("message", "HTTP " + response.code() + " 但响应体为空");
                return error;
            }
            return JSONUtil.parseObj(bodyText);
        }
    }

    private static Request buildHeaderSignedRequest(String rawUrl, String body, String ak, String sk, String region, String service) {
        Request.Builder builder = new Request.Builder().url(rawUrl)
                .addHeader("Content-Type", "application/json")
                .post(RequestBody.create(body, JSON_TYPE));
        Map<String, String> signedHeaders = signHeaderAuth(rawUrl, body, ak, sk, region, service);
        for (Map.Entry<String, String> e : signedHeaders.entrySet()) {
            builder.addHeader(e.getKey(), e.getValue());
        }
        return builder.build();
    }

    private static Request buildQuerySignedRequest(String rawUrl, String body, String ak, String sk, String region, String service) {
        String signedUrl = signQueryAuth(rawUrl, body, ak, sk, region, service);
        return new Request.Builder()
                .url(signedUrl)
                .addHeader("Content-Type", "application/json")
                .post(RequestBody.create(body, JSON_TYPE))
                .build();
    }

    private static String extractVideoUrl(JSONObject json) {
        String videoUrl = extractStr(json, "video_url");
        if (videoUrl.isEmpty()) {
            videoUrl = extractStr(json, "videoUrl");
        }
        if (videoUrl.isEmpty() && json.containsKey("data")) {
            JSONObject data = json.getJSONObject("data");
            videoUrl = extractStr(data, "video_url");
            if (videoUrl.isEmpty()) {
                videoUrl = extractStr(data, "videoUrl");
            }
            if (videoUrl.isEmpty()) {
                videoUrl = extractStr(data, "url");
            }
        }
        return videoUrl;
    }

    private static String appendQuery(String baseUrl, String query) {
        if (baseUrl.contains("?")) {
            if (baseUrl.endsWith("?") || baseUrl.endsWith("&")) {
                return baseUrl + query;
            }
            return baseUrl + "&" + query;
        }
        return baseUrl + "?" + query;
    }

    private static Map<String, String> signHeaderAuth(String rawUrl, String body, String ak, String sk, String region, String service) {
        Map<String, String> headers = new HashMap<>();
        try {
            URI uri = URI.create(rawUrl);
            String host = uri.getHost();
            String path = uri.getRawPath();
            if (path == null || path.isEmpty()) {
                path = "/";
            }

            Map<String, String> queryMap = parseQuery(uri.getRawQuery());
            String xDate = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'")
                    .withZone(ZoneOffset.UTC)
                    .format(Instant.now());
            String shortDate = xDate.substring(0, 8);
            String credentialScope = shortDate + "/" + region + "/" + service + "/request";

            String canonicalQuery = buildCanonicalQuery(queryMap);
            String payloadHash = sha256Hex(body);
            // 避免 Content-Type 值在不同客户端被追加 charset 导致签名不一致
            String signedHeaders = "host;x-content-sha256;x-date";
            String canonicalHeaders = "host:" + host + "\n"
                    + "x-content-sha256:" + payloadHash + "\n"
                    + "x-date:" + xDate + "\n";
            String canonicalRequest = "POST\n"
                    + path + "\n"
                    + canonicalQuery + "\n"
                    + canonicalHeaders + "\n"
                    + signedHeaders + "\n"
                    + payloadHash;

            String stringToSign = "HMAC-SHA256\n"
                    + xDate + "\n"
                    + credentialScope + "\n"
                    + sha256Hex(canonicalRequest);

            byte[] kDate = hmac(sk.getBytes(StandardCharsets.UTF_8), shortDate);
            byte[] kRegion = hmac(kDate, region);
            byte[] kService = hmac(kRegion, service);
            byte[] kSigning = hmac(kService, "request");
            String signature = bytesToHex(hmac(kSigning, stringToSign));
            String authorization = "HMAC-SHA256 "
                    + "Credential=" + ak + "/" + credentialScope
                    + ", SignedHeaders=" + signedHeaders
                    + ", Signature=" + signature;

            headers.put("Host", host);
            headers.put("X-Date", xDate);
            headers.put("X-Content-Sha256", payloadHash);
            headers.put("Authorization", authorization);
            return headers;
        } catch (Exception e) {
            return headers;
        }
    }

    private static String signQueryAuth(String rawUrl, String body, String ak, String sk, String region, String service) {
        try {
            URI uri = URI.create(rawUrl);
            String host = uri.getHost();
            String path = uri.getRawPath();
            if (path == null || path.isEmpty()) {
                path = "/";
            }
            Map<String, String> queryMap = parseQuery(uri.getRawQuery());
            String xDate = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'")
                    .withZone(ZoneOffset.UTC)
                    .format(Instant.now());
            String shortDate = xDate.substring(0, 8);
            String credentialScope = shortDate + "/" + region + "/" + service + "/request";
            String payloadHash = sha256Hex(body);

            queryMap.put("X-Date", xDate);
            queryMap.put("X-Algorithm", "HMAC-SHA256");
            queryMap.put("X-Credential", ak + "/" + credentialScope);
            queryMap.put("X-SignedHeaders", "host;x-content-sha256;x-date");

            String canonicalQuery = buildCanonicalQuery(queryMap);
            String canonicalHeaders = "host:" + host + "\n"
                    + "x-content-sha256:" + payloadHash + "\n"
                    + "x-date:" + xDate + "\n";
            String canonicalRequest = "POST\n"
                    + path + "\n"
                    + canonicalQuery + "\n"
                    + canonicalHeaders + "\n"
                    + "host;x-content-sha256;x-date\n"
                    + payloadHash;
            String stringToSign = "HMAC-SHA256\n"
                    + xDate + "\n"
                    + credentialScope + "\n"
                    + sha256Hex(canonicalRequest);

            byte[] kDate = hmac(sk.getBytes(StandardCharsets.UTF_8), shortDate);
            byte[] kRegion = hmac(kDate, region);
            byte[] kService = hmac(kRegion, service);
            byte[] kSigning = hmac(kService, "request");
            String signature = bytesToHex(hmac(kSigning, stringToSign));
            queryMap.put("X-Signature", signature);
            String finalQuery = buildCanonicalQuery(queryMap);
            return uri.getScheme() + "://" + host + path + "?" + finalQuery;
        } catch (Exception e) {
            return rawUrl;
        }
    }

    private static Map<String, String> parseQuery(String rawQuery) {
        Map<String, String> map = new HashMap<>();
        if (rawQuery == null || rawQuery.isEmpty()) {
            return map;
        }
        String[] pairs = rawQuery.split("&");
        for (String pair : pairs) {
            if (pair == null || pair.isEmpty()) {
                continue;
            }
            int i = pair.indexOf('=');
            String k = i >= 0 ? pair.substring(0, i) : pair;
            String v = i >= 0 ? pair.substring(i + 1) : "";
            map.put(k, v);
        }
        return map;
    }

    private static String buildCanonicalQuery(Map<String, String> queryMap) {
        List<String> keys = new ArrayList<>(queryMap.keySet());
        Collections.sort(keys);
        List<String> parts = new ArrayList<>();
        for (String key : keys) {
            parts.add(urlEncode(key) + "=" + urlEncode(defaultIfBlank(queryMap.get(key), "")));
        }
        return String.join("&", parts);
    }

    private static String urlEncode(String v) {
        try {
            String encoded = java.net.URLEncoder.encode(v, "UTF-8");
            return encoded.replace("+", "%20").replace("*", "%2A").replace("%7E", "~");
        } catch (Exception e) {
            return v;
        }
    }

    private static String defaultIfBlank(String v, String d) {
        return (v == null || v.trim().isEmpty()) ? d : v.trim();
    }

    private static boolean hasText(String v) {
        return v != null && !v.trim().isEmpty();
    }

    private static byte[] hmac(byte[] key, String content) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        return mac.doFinal(content.getBytes(StandardCharsets.UTF_8));
    }

    private static String sha256Hex(String content) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(content.getBytes(StandardCharsets.UTF_8));
        return bytesToHex(hash);
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    private static String extractStr(JSONObject json, String key) {
        if (json == null || key == null || key.isEmpty() || !json.containsKey(key)) {
            return "";
        }
        Object v = json.get(key);
        return v == null ? "" : String.valueOf(v).trim();
    }

    private static String tryDecodeBase64(String value) {
        if (!hasText(value)) {
            return "";
        }
        try {
            byte[] decoded = Base64.getDecoder().decode(value.trim());
            String s = new String(decoded, StandardCharsets.UTF_8).trim();
            return s;
        } catch (Exception e) {
            return "";
        }
    }

    private static List<String> buildSkCandidates(String sk) {
        List<String> list = new ArrayList<>();
        if (!hasText(sk)) {
            return list;
        }
        String raw = sk.trim();
        list.add(raw);
        String d1 = tryDecodeBase64(raw);
        if (hasText(d1) && !list.contains(d1)) {
            list.add(d1);
        }
        String d2 = tryDecodeBase64(d1);
        if (hasText(d2) && !list.contains(d2)) {
            list.add(d2);
        }
        return list;
    }

    private static boolean isSignatureMismatch(JSONObject json) {
        if (json == null) {
            return false;
        }
        String code = extractStr(json, "code");
        String msg = extractStr(json, "message");
        return "401".equals(code) && msg.contains("SignatureDoesNotMatch");
    }
}
