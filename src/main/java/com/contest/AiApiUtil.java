package com.contest;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 火山方舟AI调用工具
 */
public class AiApiUtil {
    private static final String API_KEY = strConfig("AI_API_KEY", strConfig("ARK_API_KEY", ""));
    private static final String API_URL = strConfig("AI_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions");
    private static final String MODEL_ENDPOINT = strConfig("AI_MODEL_ENDPOINT", "ep-m-20260310113824-5z76j");

    private static final int SCRIPT_MAX_CONTEXT = 6000;
    private static final int SCRIPT_MAX_TOKENS = 2400;
    private static final long SCRIPT_CACHE_TTL_MS = 30 * 60 * 1000L;
    private static final int SCRIPT_CACHE_MAX_SIZE = 200;
    private static volatile boolean visionEnabled = boolConfig("AI_VISION_ENABLED", true);
    private static volatile String visionApiUrl = strConfig("AI_VISION_API_URL", API_URL);
    private static volatile String visionApiKey = strConfig("AI_VISION_API_KEY", API_KEY);
    private static volatile String visionModelEndpoint = strConfig("AI_VISION_MODEL_ENDPOINT", MODEL_ENDPOINT);
    private static volatile int visionMaxSlides = intConfig("AI_VISION_MAX_SLIDES", 6);
    private static volatile int visionMaxImageBytes = intConfig("AI_VISION_MAX_IMAGE_BYTES", 5 * 1024 * 1024);

    private static final Map<String, CacheItem> SCRIPT_CACHE = new ConcurrentHashMap<>();

    // 通用超时配置
    private static final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(18, TimeUnit.SECONDS)
            .writeTimeout(18, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .build();

    // 讲稿专用通道，保留降级能力，同时给较长讲稿更多生成时间
    private static final OkHttpClient scriptClient = new OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(18, TimeUnit.SECONDS)
            .writeTimeout(12, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .build();

    private static final OkHttpClient visionClient = new OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(45, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .callTimeout(55, TimeUnit.SECONDS)
            .build();

    private static final MediaType JSON_TYPE = MediaType.parse("application/json; charset=utf-8");

    /**
     * 调用AI接口
     */
    private static String callAi(String prompt, int maxTokens) {
        return callAiInternal(prompt, maxTokens, client);
    }

    private static String callAiFast(String prompt, int maxTokens) {
        return callAiInternal(prompt, maxTokens, scriptClient);
    }

    private static String callAiInternal(String prompt, int maxTokens, OkHttpClient httpClient) {
        if (!hasText(API_KEY)) {
            return "API调用失败（未配置AI_API_KEY）";
        }
        if (!hasText(MODEL_ENDPOINT)) {
            return "API调用失败（未配置AI_MODEL_ENDPOINT）";
        }
        try {
            JSONObject body = new JSONObject();
            body.put("model", MODEL_ENDPOINT);
            body.put("temperature", 0.4f);
            body.put("max_tokens", Math.max(maxTokens, 200));

            JSONArray messages = new JSONArray();
            JSONObject msg = new JSONObject();
            msg.put("role", "user");
            msg.put("content", prompt);
            messages.add(msg);
            body.put("messages", messages);

            Request request = new Request.Builder()
                    .url(API_URL)
                    .addHeader("Authorization", "Bearer " + API_KEY)
                    .addHeader("Content-Type", "application/json")
                    .post(RequestBody.create(body.toString(), JSON_TYPE))
                    .build();

            try (Response response = httpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    return "API调用失败（状态码：" + response.code() + "）";
                }
                String bodyStr = response.body() == null ? "" : response.body().string();
                if (bodyStr.trim().isEmpty()) {
                    return "API调用失败（空响应）";
                }
                JSONObject result = JSONUtil.parseObj(bodyStr);
                return result.getJSONArray("choices")
                        .getJSONObject(0)
                        .getJSONObject("message")
                        .getStr("content");
            }
        } catch (IOException e) {
            String msg = e.getMessage() == null ? "未知网络异常" : e.getMessage();
            return "网络异常/超时：" + msg;
        } catch (Exception e) {
            return "网络异常/超时：" + (e.getMessage() == null ? "unknown" : e.getMessage());
        }
    }

    public static void configureVision(
            boolean enabled,
            String apiUrl,
            String apiKey,
            String modelEndpoint,
            int maxSlides,
            int maxImageBytes
    ) {
        visionEnabled = enabled;
        if (hasText(apiUrl)) {
            visionApiUrl = apiUrl.trim();
        }
        if (hasText(apiKey)) {
            visionApiKey = apiKey.trim();
        }
        if (hasText(modelEndpoint)) {
            visionModelEndpoint = modelEndpoint.trim();
        }
        if (maxSlides >= 0) {
            visionMaxSlides = maxSlides;
        }
        if (maxImageBytes > 0) {
            visionMaxImageBytes = maxImageBytes;
        }
    }

    public static int getVisionMaxSlides() {
        return Math.max(0, visionMaxSlides);
    }

    public static boolean isVisionEnabled() {
        return visionEnabled && getVisionMaxSlides() > 0;
    }

    public static String describeSlideImage(Path imagePath, String slideText, int pageNum) {
        if (!visionEnabled || getVisionMaxSlides() <= 0) {
            return "未开启图片识别（ai.vision.enabled=false）";
        }
        if (imagePath == null) {
            return "缺少页面预览图，无法识别";
        }
        String effectiveKey = hasText(visionApiKey) ? visionApiKey : API_KEY;
        String effectiveModel = hasText(visionModelEndpoint) ? visionModelEndpoint : MODEL_ENDPOINT;
        if (!hasText(effectiveKey)) {
            return "未配置 AI_API_KEY / AI_VISION_API_KEY，无法识别图片内容";
        }
        if (!hasText(effectiveModel)) {
            return "未配置 AI_MODEL_ENDPOINT / AI_VISION_MODEL_ENDPOINT，无法识别图片内容";
        }
        try {
            if (!Files.exists(imagePath) || !Files.isRegularFile(imagePath)) {
                return "页面预览图不存在：" + imagePath.getFileName();
            }
            long size = Files.size(imagePath);
            if (size <= 0) {
                return "页面预览图为空，无法识别";
            }
            if (size > Math.max(1, visionMaxImageBytes)) {
                return "页面预览图过大（" + (size / 1024) + "KB），超过限制";
            }

            String imageBase64 = Base64.getEncoder().encodeToString(Files.readAllBytes(imagePath));
            String prompt = "请识别并概括这页PPT图片中的教学信息。要求："
                    + "1. 优先提取图中的文字、流程、图表趋势、结构关系；"
                    + "2. 输出适合放入课堂讲稿和问答上下文的中文描述；"
                    + "3. 不要编造看不清或图中不存在的内容；"
                    + "4. 控制在160字以内，必须有实质内容。"
                    + "\n当前页码：第" + pageNum + "页"
                    + "\n页面已有文本：\n" + limitText(slideText, 800);

            JSONObject body = new JSONObject();
            body.put("model", effectiveModel);
            body.put("temperature", 0.2f);
            body.put("max_tokens", 600);

            JSONArray content = new JSONArray();
            JSONObject textPart = new JSONObject();
            textPart.put("type", "text");
            textPart.put("text", prompt);
            content.add(textPart);

            JSONObject imageUrl = new JSONObject();
            imageUrl.put("url", "data:image/png;base64," + imageBase64);
            JSONObject imagePart = new JSONObject();
            imagePart.put("type", "image_url");
            imagePart.put("image_url", imageUrl);
            content.add(imagePart);

            JSONArray messages = new JSONArray();
            JSONObject msg = new JSONObject();
            msg.put("role", "user");
            msg.put("content", content);
            messages.add(msg);
            body.put("messages", messages);

            Request request = new Request.Builder()
                    .url(hasText(visionApiUrl) ? visionApiUrl : API_URL)
                    .addHeader("Authorization", "Bearer " + effectiveKey)
                    .addHeader("Content-Type", "application/json")
                    .post(RequestBody.create(body.toString(), JSON_TYPE))
                    .build();

            try (Response response = visionClient.newCall(request).execute()) {
                String bodyStr = response.body() == null ? "" : response.body().string();
                if (!response.isSuccessful()) {
                    String errHint = limitText(bodyStr.replaceAll("\\s+", " "), 180);
                    return "识别失败（HTTP " + response.code() + (errHint.isEmpty() ? "" : "：" + errHint) + "）";
                }
                if (bodyStr.trim().isEmpty()) {
                    return "识别失败：接口返回空响应";
                }
                JSONObject result = JSONUtil.parseObj(bodyStr);
                String contentText = result.getJSONArray("choices")
                        .getJSONObject(0)
                        .getJSONObject("message")
                        .getStr("content");
                String normalized = normalizeVisionText(contentText);
                if (!hasText(normalized)) {
                    return "识别失败：模型未返回有效文字";
                }
                return normalized;
            }
        } catch (Exception e) {
            String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage().trim();
            return "识别异常：" + limitText(msg, 160);
        }
    }

    /**
     * 生成讲稿（优先快速AI，失败自动本地降级，保证可返回）
     */
    public static String generateLectureScript(String pptText) {
        if (pptText == null || pptText.trim().isEmpty()) {
            return "⚠️ 未获取到PPT有效内容，请：\n1. 确认PPT文件包含文本内容\n2. 重新解析PPT文件\n3. 检查PPT是否为加密/损坏文件";
        }

        String normalized = pptText.trim();
        String limitedText = normalized.length() > SCRIPT_MAX_CONTEXT ? normalized.substring(0, SCRIPT_MAX_CONTEXT) : normalized;
        // teach-v4：过滤教务/书目杂质，口播像真老师
        String cacheKey = "teach-v4:" + md5Hex(limitedText);

        String cached = getScriptCache(cacheKey);
        if (cached != null && !looksLikeBadTeachingScript(cached)) {
            return cached;
        }

        String prompt = "你是一名真实课堂里的专业教师。请根据课件提纲撰写「可直接口播」的讲稿，听起来像老师在讲课。\n"
                + "硬性要求：\n"
                + "1. 禁止照抄课件原句；禁止朗读书名、出版社、版次、作者、ISBN、网址、考核细则、学时学分等教务信息。\n"
                + "2. 这些信息若出现在提纲里，最多用一句话带过（例如「教材和考核方式课上会说明」），不要展开成知识点。\n"
                + "3. 按页分段：每一页单独一行写「第N页」，不要用多余等号或特殊符号装饰。\n"
                + "4. 每一页用自然口语讲：是什么 → 为什么学 → 一个生活/代码小例子 → 一句「大家想一想…」。\n"
                + "5. 全稿穿插 1～2 道简短互动题（问/A/B/C/D/答案/解析），题目要针对本课知识，不要空泛套话。\n"
                + "6. 不要反复说「课件只是提纲」「老师换个说法」这类模板句；每页表述要有变化。\n"
                + "7. 输出纯中文口播正文，不要 Markdown 标题符号，不要表情符号。\n\n"
                + "课件提纲（仅作知识锚点）：\n" + limitedText;

        String script = callAiFast(prompt, SCRIPT_MAX_TOKENS);
        if (!isAiCallFailure(script) && !looksLikeBadTeachingScript(script)) {
            script = polishTeachingScript(script);
            putScriptCache(cacheKey, script);
            return script;
        }

        String fallback = buildFallbackScript(limitedText);
        putScriptCache(cacheKey, fallback);
        return fallback;
    }

    /** 仅本地生成教学口播稿（不调用 AI），用于降级或检测到「复读 PPT」时。 */
    public static String localTeachingScript(String pptText) {
        String normalized = pptText == null ? "" : pptText.trim();
        if (normalized.isEmpty()) {
            return "同学们好。今天我们先把学习目标说清楚：听完课，你要能用自己的话说明「学什么、为什么学、怎么上手试一下」。\n\n"
                    + "【互动题】\n问：听课更有效的做法是？\nA. 带着问题理解，并能复述要点\nB. 只抄标题\nC. 不思考只听\nD. 只背最后一页\n答案：A\n解析：能复述和举例，才说明听懂了。";
        }
        String limitedText = normalized.length() > SCRIPT_MAX_CONTEXT ? normalized.substring(0, SCRIPT_MAX_CONTEXT) : normalized;
        return buildFallbackScript(limitedText);
    }

    /** 检测套话模板、书目照读、杂质过多等不合格讲稿。 */
    public static boolean looksLikeBadTeachingScript(String script) {
        if (script == null || script.trim().isEmpty()) {
            return true;
        }
        String s = script.trim();
        if (s.contains("老师换个说法：它提醒我们在真实学习或项目里")) {
            return true;
        }
        if (s.contains("课件上的字只是提纲，老师讲的内容和课件不会一字不差")) {
            return true;
        }
        if (s.contains("如果只把标题背下来，其实还没学会；关键是弄清它要解决什么问题")) {
            return true;
        }
        int metaHits = 0;
        for (String line : s.split("\\r?\\n")) {
            String t = line.trim();
            if (t.isEmpty() || isQuizLine(t)) {
                continue;
            }
            // 正文里大段照读书目/出版社才算不合格
            if (t.contains("出版社") || (t.contains("第") && t.contains("版") && t.length() > 16)
                    || t.startsWith("考核方式") || t.contains("ISBN")) {
                metaHits++;
            }
        }
        return metaHits >= 2;
    }

    private static boolean isQuizLine(String t) {
        return t.startsWith("【互动题】")
                || t.startsWith("问：")
                || t.startsWith("答案")
                || t.startsWith("解析")
                || t.matches("^[A-D][.、\\s].*");
    }

    /**
     * AI问答
     */
    public static String answerStudentQuestion(String question, String pptContext) {
        if (pptContext == null || pptContext.trim().isEmpty()) {
            return "⚠️ 未获取到PPT有效内容，请先解析包含文本的PPT文件！";
        }
        if (question == null || question.trim().isEmpty()) {
            return "⚠️ 请输入有效的问题！";
        }

        String limitedContext = pptContext.length() > 3000 ? pptContext.substring(0, 3000) : pptContext;

        String prompt = "你是讲课老师，请严格根据以下PPT内容回答学生问题，要求：\n" +
                "1. 回答准确、紧扣PPT内容，并在必要时适度展开说明\n" +
                "2. 不要编造PPT中没有的信息\n" +
                "3. 优先用2到4个自然段回答，可补充关键概念、原因或课堂例子，但不要跑题\n" +
                "4. 不要提及\"空文件\"等无关表述\n\n" +
                "PPT内容：\n" + limitedContext + "\n\n" +
                "学生问题：" + question;

        String answer = callAi(prompt, 1400);
        if (!isAiCallFailure(answer)) {
            return answer;
        }
        return buildFallbackAnswer(question, limitedContext);
    }

    public static String generateComputerLectureScript(
            String courseType,
            String programmingLanguage,
            String teachingGoal,
            String pptText,
            String resourceContext
    ) {
        String course = hasText(courseType) ? courseType : "计算机课程";
        String language = hasText(programmingLanguage) ? programmingLanguage : "课程相关语言";
        String context = limitText((pptText == null ? "" : pptText) + "\n" + (resourceContext == null ? "" : resourceContext), 10000);
        String prompt = "你是一名高校计算机课程的真实授课教师。请撰写可直接口播的讲稿，像课堂讲授。\n"
                + "课程类型：" + course + "\n"
                + "主要语言：" + language + "\n"
                + "教学目标：" + (hasText(teachingGoal) ? teachingGoal : "帮助学生理解知识并能完成实践") + "\n"
                + "要求：禁止照抄提纲；禁止展开书名出版社版次、考核细则等教务信息；"
                + "分页只用单独一行「第N页」；每页白话解释+例子+思考问；穿插1～2道互动题；"
                + "不要套话模板，不要多余符号。代码解释须结合资料，不编造。约8到10分钟。\n\n"
                + "课程资料（锚点）：\n" + context;
        String answer = callAiFast(prompt, SCRIPT_MAX_TOKENS);
        if (!isAiCallFailure(answer) && !looksLikeBadTeachingScript(answer)) {
            return polishTeachingScript(answer);
        }
        return polishTeachingScript(buildComputerFallbackScript(course, language, teachingGoal, context));
    }

    public static String answerComputerQuestion(
            String courseType,
            String programmingLanguage,
            String questionType,
            String question,
            String pptText,
            String resourceContext,
            String knowledgeContext
    ) {
        String mode = hasText(questionType) ? questionType : "concept";
        String strategy;
        if ("debug".equals(mode)) {
            strategy = "先指出最可能的错误范围，再解释原因，接着给修改方向和验证步骤。默认只给一级提示，不直接替学生输出完整答案。";
        } else if ("code".equals(mode)) {
            strategy = "结合真实文件、类、方法或SQL逐步解释调用和数据流；不存在的代码不得编造。";
        } else {
            strategy = "先解释概念，再说明它在当前代码或实验中的作用，最后给一个检查理解的问题。";
        }
        String prompt = "你是一名高校计算机课程助教。\n"
                + "课程：" + (hasText(courseType) ? courseType : "计算机课程") + "\n"
                + "语言：" + (hasText(programmingLanguage) ? programmingLanguage : "未指定") + "\n"
                + "问答模式：" + mode + "\n"
                + "回答策略：" + strategy + "\n"
                + "回答必须基于下面的当前课程资料，并在结尾用“依据：”注明引用的文件或课件；"
                + "资料不足时明确说明缺少什么，不使用其他学科知识库答案。\n\n"
                + "课件上下文：\n" + limitText(pptText, 3500)
                + "\n\n当前项目代码/实验/日志上下文：\n" + limitText(resourceContext, 4500)
                + "\n\n按课程检索到的权威知识片段：\n" + limitText(knowledgeContext, 7500)
                + "\n\n学生问题：" + question;
        String answer = callAi(prompt, 1600);
        if (!isAiCallFailure(answer)) {
            return answer;
        }
        return buildComputerFallbackAnswer(mode, question, pptText, resourceContext, knowledgeContext);
    }

    private static boolean isAiCallFailure(String text) {
        if (text == null || text.trim().isEmpty()) {
            return true;
        }
        return text.startsWith("API调用失败")
                || text.startsWith("网络异常")
                || text.startsWith("❌")
                || text.startsWith("⚠️");
    }

    private static String getScriptCache(String key) {
        CacheItem item = SCRIPT_CACHE.get(key);
        if (item == null) {
            return null;
        }
        if (System.currentTimeMillis() - item.ts > SCRIPT_CACHE_TTL_MS) {
            SCRIPT_CACHE.remove(key);
            return null;
        }
        return item.value;
    }

    private static void putScriptCache(String key, String value) {
        if (SCRIPT_CACHE.size() >= SCRIPT_CACHE_MAX_SIZE) {
            long now = System.currentTimeMillis();
            Iterator<Map.Entry<String, CacheItem>> it = SCRIPT_CACHE.entrySet().iterator();
            while (it.hasNext()) {
                Map.Entry<String, CacheItem> e = it.next();
                if (now - e.getValue().ts > SCRIPT_CACHE_TTL_MS) {
                    it.remove();
                }
            }
            if (SCRIPT_CACHE.size() >= SCRIPT_CACHE_MAX_SIZE) {
                Iterator<String> keyIt = SCRIPT_CACHE.keySet().iterator();
                if (keyIt.hasNext()) {
                    SCRIPT_CACHE.remove(keyIt.next());
                }
            }
        }
        SCRIPT_CACHE.put(key, new CacheItem(value, System.currentTimeMillis()));
    }

    private static String md5Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return String.valueOf(input.hashCode());
        }
    }

    private static String normalizeVisionText(String text) {
        if (text == null) {
            return "";
        }
        String normalized = text.replace('\u000B', '\n')
                .replaceAll("\\s+", " ")
                .trim();
        if (isAiCallFailure(normalized)) {
            return "";
        }
        return normalized;
    }

    private static String limitText(String text, int limit) {
        if (text == null) {
            return "";
        }
        String value = text.trim();
        if (value.length() <= limit) {
            return value;
        }
        return value.substring(0, limit);
    }

    private static volatile java.util.Properties localConfigProps;

    private static String strConfig(String key, String defaultValue) {
        String value = System.getProperty(key);
        if (!hasText(value)) {
            value = System.getenv(key);
        }
        if (!hasText(value)) {
            // Spring 风格键：AI_API_KEY -> ai.api.key（可选）
            String dotted = key.toLowerCase().replace('_', '.');
            value = System.getProperty(dotted);
            if (!hasText(value)) {
                value = loadLocalConfig(key);
            }
            if (!hasText(value)) {
                value = loadLocalConfig(dotted);
            }
        }
        return hasText(value) ? value.trim() : defaultValue;
    }

    private static String loadLocalConfig(String key) {
        try {
            java.util.Properties props = localConfigProps;
            if (props == null) {
                props = new java.util.Properties();
                Path[] candidates = new Path[] {
                        Path.of("config", "application-local.properties"),
                        Path.of("application-local.properties")
                };
                for (Path candidate : candidates) {
                    if (Files.isRegularFile(candidate)) {
                        try (InputStream in = Files.newInputStream(candidate)) {
                            props.load(new java.io.InputStreamReader(in, StandardCharsets.UTF_8));
                        }
                        break;
                    }
                }
                localConfigProps = props;
            }
            String value = props.getProperty(key);
            return hasText(value) ? value.trim() : "";
        } catch (Exception e) {
            return "";
        }
    }

    private static int intConfig(String key, int defaultValue) {
        String value = strConfig(key, "");
        if (!hasText(value)) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private static boolean boolConfig(String key, boolean defaultValue) {
        String value = strConfig(key, "");
        if (!hasText(value)) {
            return defaultValue;
        }
        return "true".equalsIgnoreCase(value)
                || "1".equals(value.trim())
                || "yes".equalsIgnoreCase(value)
                || "on".equalsIgnoreCase(value);
    }

    private static boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private static class CacheItem {
        private final String value;
        private final long ts;

        private CacheItem(String value, long ts) {
            this.value = value;
            this.ts = ts;
        }
    }

    private static String buildFallbackScript(String text) {
        Pattern pagePat = Pattern.compile("^=+\\s*第(\\d+)页\\s*=+$");
        String[] raw = text.split("\\r?\\n");
        List<List<String>> pages = new ArrayList<>();
        List<String> current = new ArrayList<>();
        for (String s : raw) {
            String t = s == null ? "" : s.trim();
            if (t.isEmpty()) {
                continue;
            }
            Matcher pm = pagePat.matcher(t);
            if (pm.matches()) {
                if (!current.isEmpty()) {
                    pages.add(current);
                }
                current = new ArrayList<>();
                current.add("PAGE:" + pm.group(1));
            } else if (!isNonTeachingLine(t)) {
                if (current.isEmpty()) {
                    current.add("PAGE:1");
                }
                current.add(t);
            }
        }
        if (!current.isEmpty()) {
            pages.add(current);
        }
        if (pages.isEmpty()) {
            pages.add(List.of("PAGE:1", "本节课程"));
        }

        String courseTitle = "本节课程";
        for (List<String> page : pages) {
            for (int i = 1; i < page.size(); i++) {
                courseTitle = cleanTitle(page.get(i));
                break;
            }
            break;
        }

        boolean pythonish = (courseTitle + "\n" + text).toLowerCase(java.util.Locale.ROOT).contains("python");
        StringBuilder sb = new StringBuilder();
        sb.append("同学们好，今天我们学习《").append(courseTitle).append("》。\n");
        if (pythonish) {
            sb.append("先别急着记名词。学完这节，你要能说清：Python 是做什么的、为什么很多人入门选它、以及怎样开始写第一行代码。\n\n");
        } else {
            sb.append("听课目标很明确：弄清这一节要解决什么问题，并能用自己的话举一个例子。\n\n");
        }

        int spokenPages = 0;
        for (List<String> page : pages) {
            String pageNo = "1";
            List<String> points = new ArrayList<>();
            for (String line : page) {
                if (line.startsWith("PAGE:")) {
                    pageNo = line.substring(5);
                } else {
                    String cleaned = cleanTitle(line);
                    if (!cleaned.isEmpty() && !isNonTeachingLine(cleaned)) {
                        points.add(cleaned);
                    }
                }
            }
            if (points.isEmpty()) {
                continue;
            }
            String pageTitle = points.get(0);
            List<String> teachPoints = new ArrayList<>();
            for (int i = 1; i < points.size() && teachPoints.size() < 4; i++) {
                teachPoints.add(points.get(i));
            }

            spokenPages++;
            sb.append("第").append(pageNo).append("页\n");
            sb.append(narratePage(pageTitle, teachPoints, pythonish, spokenPages));
            sb.append("\n");

            if (spokenPages % 3 == 0) {
                sb.append(buildTopicQuiz(pageTitle, pythonish));
                sb.append("\n");
            }
        }

        if (spokenPages == 0) {
            sb.append("第1页\n");
            sb.append(narratePage(courseTitle, List.of(), pythonish, 1));
            sb.append("\n");
            spokenPages = 1;
        }

        if (spokenPages % 3 != 0) {
            sb.append(buildTopicQuiz(courseTitle, pythonish));
            sb.append("\n");
        }
        sb.append("今天先到这里。课后请用三句话复盘：学了什么、为什么重要、你准备怎么动手试一次。下节课我们继续。");
        return polishTeachingScript(sb.toString());
    }

    private static String narratePage(String pageTitle, List<String> teachPoints, boolean pythonish, int order) {
        String title = pageTitle == null ? "" : pageTitle.trim();
        if (title.isEmpty()) {
            title = "这一部分";
        }
        String key = title.toLowerCase(java.util.Locale.ROOT);
        StringBuilder sb = new StringBuilder();

        if (order == 1 || key.contains("python") && (key.contains("\u521d\u8bc6") || key.contains("\u5f15\u8a00") || key.contains("\u6982\u8ff0") || order == 1)) {
            if (pythonish) {
                sb.append("我们先从「").append(title).append("」聊起。");
                sb.append("Python 可以把它理解成一门更贴近人话的编程语言：同样要实现一个小功能，代码往往更短、更好读。");
                sb.append("所以它特别适合入门，也适合写数据处理、自动化这类实际任务。");
                sb.append("大家想一想：如果让你统计一份成绩单里的平均分，你更希望写十行就能看懂的程序，还是写很长却难读的程序？");
            } else {
                sb.append("我们先进入「").append(title).append("」。");
                sb.append("这一页的任务不是背标题，而是建立整体印象：它属于哪类问题、学完后你能解决什么。");
                sb.append("请带着一个问题听：如果用一句话向同学介绍今天的主题，你会怎么说？");
            }
        } else if (pythonish && (key.contains("\u5173\u4e8e") || key.contains("\u7b80\u4ecb") || key.contains("\u4ecb\u7ecd") || key.contains("python"))) {
            sb.append("接下来讲「").append(title).append("」。");
            sb.append("Python 常见的优点是：语法清晰、生态丰富、上手快。");
            sb.append("课堂里我们会用它写小例子，先跑通，再理解为什么这样写。");
            sb.append("书名、版本这些信息课下查阅即可，课堂上我们把精力放在会写、会改、会验证。");
            sb.append("想一想：你理想中的第一节编程课，结束时最希望自己已经完成哪一件小事？");
        } else if (key.contains("\u5b89\u88c5") || key.contains("\u73af\u5883") || key.contains("\u5de5\u5177")) {
            sb.append("到「").append(title).append("」了。");
            sb.append("环境准备可以记一句口诀：装好、能运行、能看到输出。");
            sb.append("如果运行失败，先看报错第一行在说什么，再检查路径和版本，不要一上来就重装系统。");
            sb.append("大家可以先自问：我这台电脑上，怎样确认程序真的跑起来了？");
        } else if (key.contains("\u8bed\u6cd5") || key.contains("\u53d8\u91cf") || key.contains("\u6570\u636e\u7c7b\u578b") || key.contains("\u8fd0\u7b97\u7b26")) {
            sb.append("我们看「").append(title).append("」。");
            sb.append("这里最容易犯的错，是只记名字不练手。");
            sb.append("建议你每学一个概念就立刻改一个数字、改一个名字，观察输出有什么变化。");
            sb.append("想一想：如果把例子里的数据换成你自己的学号或姓名，结果会怎样变？");
        } else {
            sb.append("下面进入「").append(title).append("」。");
            if (!teachPoints.isEmpty()) {
                sb.append("这一页我抓住");
                sb.append(Math.min(2, teachPoints.size()));
                sb.append("个要点来说。");
                for (int i = 0; i < teachPoints.size() && i < 2; i++) {
                    String p = teachPoints.get(i);
                    sb.append(i == 0 ? "第一，" : "第二，");
                    sb.append(expandTeachPoint(p, pythonish));
                }
            } else if (pythonish) {
                sb.append("请记住：先让程序跑起来，再问为什么这样写；书名和考核细则不必在口播里展开。");
            } else {
                sb.append("请抓住核心：它要解决什么问题，以及你会在什么场景用到它。");
            }
            sb.append("听完这一段，试着用自己的话复述二十秒。");
        }
        sb.append('\n');
        return sb.toString();
    }

    private static String expandTeachPoint(String point, boolean pythonish) {
        String p = cleanTitle(point);
        if (p.isEmpty()) {
            return "把概念放回具体例子里理解。";
        }
        if (pythonish && (p.toLowerCase(java.util.Locale.ROOT).contains("python") || p.contains("程序"))) {
            return "围绕「" + p + "」，先弄清它能帮你完成哪类任务，再看最小示例怎么写、怎么验证。";
        }
        if (p.contains("课程") || p.contains("介绍")) {
            return "先明确学习路径：从会运行到会改错，再到能完成小练习。";
        }
        return "关于「" + p + "」，重点不是背定义，而是能判断它在什么情况下有用、做错了怎么排查。";
    }

    private static String buildTopicQuiz(String topic, boolean pythonish) {
        String t = cleanTitle(topic);
        if (t.length() > 24) {
            t = t.substring(0, 24);
        }
        StringBuilder sb = new StringBuilder();
        sb.append("【互动题】\n");
        if (pythonish) {
            sb.append("问：开始学习 Python 时，更合理的目标是？\n");
            sb.append("A. 能写小程序、看懂报错并验证结果\n");
            sb.append("B. 只背书名和封面信息\n");
            sb.append("C. 只抄课件标题\n");
            sb.append("D. 不运行代码，只看不做\n");
            sb.append("答案：A\n");
            sb.append("解析：编程课的核心是动手与验证，不是记教务信息。\n");
        } else {
            sb.append("问：学习「").append(t).append("」时，怎样才算听懂？\n");
            sb.append("A. 能解释它解决什么问题，并举一个例子\n");
            sb.append("B. 只记住课件上的原句\n");
            sb.append("C. 只关心页数和标题\n");
            sb.append("D. 不复盘，考试前再看\n");
            sb.append("答案：A\n");
            sb.append("解析：能解释、能举例，才说明真正理解。\n");
        }
        return sb.toString();
    }

    private static boolean isNonTeachingLine(String line) {
        if (line == null) {
            return true;
        }
        String t = line.trim();
        if (t.isEmpty()) {
            return true;
        }
        // 口播长句不做杂质过滤，避免误删正文
        if (t.length() > 36) {
            return false;
        }
        if (t.matches("^=+\\s*第\\d+页\\s*=+$") || t.matches("^第\\s*\\d+\\s*页$")) {
            return false;
        }
        String lower = t.toLowerCase(java.util.Locale.ROOT);
        if (lower.contains("http://") || lower.contains("https://") || lower.contains("www.")) {
            return true;
        }
        if (t.contains("出版社") || t.contains("ISBN") || t.contains("isbn")
                || t.matches(".*第\\s*\\d+\\s*版.*")
                || t.contains("人民邮电") || t.contains("高等教育出版社") || t.contains("清华大学出版社")
                || t.contains("电子工业出版社") || t.contains("机械工业出版社")) {
            return true;
        }
        if (t.contains("主编") || t.contains("编著") || t.contains("著.") || t.contains("等.")
                || (t.contains("刘") && t.contains("人民")) || t.matches(".*\\d{4}\\s*年.*出版社.*")) {
            return true;
        }
        if (t.matches("^(考核|成绩|学分|学时|学号|班级|姓名|日期)([方式标准构成].*)?$")
                || t.startsWith("考核方式") || t.startsWith("成绩构成") || t.startsWith("学时安排")) {
            return true;
        }
        // 过长且像书目/落款
        if (t.length() >= 28 && (t.contains("出版社") || t.contains("第") && t.contains("版") || t.contains("编著"))) {
            return true;
        }
        return false;
    }

    private static String cleanTitle(String raw) {
        if (raw == null) {
            return "";
        }
        String t = raw.trim()
                .replaceAll("^[=\\-—_\\s]+", "")
                .replaceAll("[=\\-—_\\s]+$", "")
                .replaceAll("[#*`>~]+", "")
                .replaceAll("\\s+", " ")
                .trim();
        if (isNonTeachingLine(t)) {
            return "";
        }
        return t;
    }

    private static String polishTeachingScript(String script) {
        if (script == null) {
            return "";
        }
        String[] lines = script.replace("\r\n", "\n").replace('\r', '\n').split("\n", -1);
        StringBuilder out = new StringBuilder();
        for (String line : lines) {
            String t = line == null ? "" : line.trim();
            if (t.isEmpty()) {
                if (out.length() > 0 && out.charAt(out.length() - 1) != '\n') {
                    out.append('\n');
                }
                continue;
            }
            // 统一分页标记，去掉装饰等号
            Matcher m = Pattern.compile("^[=\\s]*第\\s*(\\d+)\\s*页[=\\s]*$").matcher(t);
            if (m.matches()) {
                out.append("第").append(m.group(1)).append("页\n");
                continue;
            }
            if (!isQuizLine(t) && isNonTeachingLine(t)) {
                continue;
            }
            // 去掉明显套话
            if (t.contains("老师换个说法：它提醒我们在真实学习或项目里")) {
                continue;
            }
            if (t.contains("课件上的字只是提纲，老师讲的内容和课件不会一字不差")) {
                continue;
            }
            out.append(t).append('\n');
        }
        return out.toString().trim();
    }

    private static String buildFallbackAnswer(String question, String context) {
        List<String> lines = collectContextLines(context, 10);
        if (lines.isEmpty()) {
            return "当前网络不稳定，AI 问答已自动切换到本地模式。当前课件文本较少，建议先确认 PPT 已完成解析，再重新提问。";
        }

        String title = lines.get(0);
        StringBuilder sb = new StringBuilder();
        sb.append("当前网络不稳定，AI 问答已自动切换到本地模式。\n\n");

        if (question != null && question.contains("概念")) {
            sb.append("这节课主要围绕《").append(title).append("》中的核心概念展开。");
        } else {
            sb.append("根据当前课件内容，这个问题可以从《").append(title).append("》的主题出发理解。");
        }

        if (lines.size() > 1) {
            sb.append("课件中比较关键的内容包括：");
            int count = Math.min(lines.size() - 1, 5);
            for (int i = 1; i <= count; i++) {
                if (i > 1) {
                    sb.append("；");
                }
                sb.append(lines.get(i));
            }
            sb.append("。\n\n");
        } else {
            sb.append("\n\n");
        }

        sb.append("你可以先把它理解为：本节课不是只记一个定义，而是要弄清楚这些概念解决什么问题、彼此之间有什么关系，以及在实际学习或应用中应该怎样使用。");
        sb.append("复习时建议按“概念是什么、为什么重要、如何应用”三个问题来整理。");
        return sb.toString();
    }

    private static String buildComputerFallbackScript(String course, String language, String teachingGoal, String context) {
        List<String> lines = collectContextLines(context, 8);
        String focus = lines.isEmpty() ? "当前课程资料" : String.join("；", lines);
        return "# 学习目标\n"
                + (hasText(teachingGoal) ? teachingGoal : "理解本节知识并能够结合代码或实验完成验证。") + "\n\n"
                + "# 核心概念\n本节属于" + course + "，主要使用" + language
                + "。学习时需要同时关注概念、实现过程和运行结果。\n\n"
                + "# 代码与执行过程\n请围绕以下已解析资料逐步定位类、方法、SQL或实验步骤：\n" + focus + "\n\n"
                + "# 常见错误\n重点检查命名、依赖、路径、参数、数据类型和运行环境是否与课程要求一致。\n\n"
                + "# 课堂实验\n选择一个最小示例，先预测运行结果，再执行或人工检查，并记录实际结果与预期结果的差异。\n\n"
                + "# 检查问题\n你能否说明这段实现解决什么问题、关键步骤在哪里，以及出现错误时先检查什么？";
    }

    static String buildComputerFallbackAnswer(
            String mode,
            String question,
            String pptText,
            String resourceContext,
            String knowledgeContext
    ) {
        List<String> resourceLines = collectContextLines(resourceContext, 6);
        List<String> pptLines = collectContextLines(pptText, 4);
        List<String> knowledgeSnippets = collectKnowledgeSnippets(knowledgeContext, question, 5);
        String evidence = !resourceLines.isEmpty()
                ? String.join("；", resourceLines)
                : String.join("；", pptLines);
        String knowledgeEvidence = knowledgeSnippets.isEmpty()
                ? ""
                : "\n- " + String.join("\n- ", knowledgeSnippets);
        String basis = !knowledgeSnippets.isEmpty()
                ? "当前课程知识库" + (!resourceLines.isEmpty() ? "与项目资料" : "")
                : (!resourceLines.isEmpty() ? "当前项目资料" : "当前课程课件");
        if ("debug".equals(mode)) {
            return "当前已进入调试指导模式。\n\n"
                    + "一级提示：先根据异常名称、首个业务代码行和实际输出定位错误范围，不要一次修改多个位置。"
                    + "建议依次检查输入参数、空值、类型、路径或数据库连接配置，再重新运行验证。\n\n"
                    + "当前可用线索：" + (evidence.isEmpty() ? "资料不足，请补充完整错误日志和相关代码。" : evidence)
                    + (knowledgeEvidence.isEmpty() ? "" : "\n\n权威知识线索：" + knowledgeEvidence)
                    + "\n\n依据：" + basis + "。";
        }
        if ("code".equals(mode)) {
            return "这个问题需要沿着“入口、调用、数据变化、输出”四步阅读代码。"
                    + "先找到入口方法，再跟踪它调用的类或SQL，最后核对返回值与页面或控制台结果。\n\n"
                    + "当前资料线索：" + (evidence.isEmpty() ? "尚未上传可引用的代码资料。" : evidence)
                    + (knowledgeEvidence.isEmpty() ? "" : "\n\n权威知识线索：" + knowledgeEvidence)
                    + "\n\n依据：" + basis + "。";
        }
        return "可以先从“概念是什么、解决什么问题、在当前课程中如何使用”三个层次理解。"
                + "当前问题是：" + question + "。\n\n"
                + "课程线索：" + (evidence.isEmpty() ? "当前资料不足，请补充对应课件或实验材料。" : evidence)
                + (knowledgeEvidence.isEmpty() ? "" : "\n\n权威知识线索：" + knowledgeEvidence)
                + "\n\n依据：" + basis + "。";
    }

    private static List<String> collectKnowledgeSnippets(String text, String question, int limit) {
        List<String> snippets = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return snippets;
        }
        String[] blocks = text.split("(?=【知识片段\\s+\\d+】)");
        for (String block : blocks) {
            if (block == null || block.isBlank() || !block.contains("【知识片段")) {
                continue;
            }
            String document = findContextValue(block, "文档：");
            String section = findContextValue(block, "章节：");
            String source = findContextValue(block, "来源：");
            int contentIndex = block.indexOf("\n内容：\n");
            String content = contentIndex >= 0
                    ? block.substring(contentIndex + "\n内容：\n".length())
                    : findContextValue(block, "内容：");
            content = selectRelevantWindow(content.replaceAll("\\s+", " ").trim(), question, 280);
            if (content.isBlank()) {
                continue;
            }
            StringBuilder snippet = new StringBuilder();
            if (!document.isBlank()) {
                snippet.append(document);
            }
            if (!section.isBlank()) {
                if (snippet.length() > 0) snippet.append(" / ");
                snippet.append(section);
            }
            if (snippet.length() > 0) {
                snippet.append("：");
            }
            snippet.append(content);
            if (!source.isBlank()) {
                snippet.append("（来源：").append(source).append("）");
            }
            snippets.add(snippet.toString());
            if (snippets.size() >= limit) {
                break;
            }
        }
        return snippets;
    }

    private static String selectRelevantWindow(String content, String question, int maxLength) {
        if (content == null || content.length() <= maxLength) {
            return content == null ? "" : content;
        }
        String normalized = content.toLowerCase();
        List<String> queryTokens = new ArrayList<>();
        Matcher matcher = Pattern.compile("[a-z0-9_.$-]{3,}")
                .matcher(question == null ? "" : question.toLowerCase());
        while (matcher.find()) {
            queryTokens.add(matcher.group());
        }
        int focus = -1;
        for (int i = queryTokens.size() - 1; i >= 0; i--) {
            int index = normalized.indexOf(queryTokens.get(i));
            if (index >= 0) {
                focus = index;
                break;
            }
        }
        int start = focus < 0 ? 0 : Math.max(0, focus - 90);
        if (start + maxLength > content.length()) {
            start = Math.max(0, content.length() - maxLength);
        }
        String window = content.substring(start, Math.min(content.length(), start + maxLength));
        return (start > 0 ? "..." : "") + window + (start + maxLength < content.length() ? "..." : "");
    }

    private static String findContextValue(String block, String prefix) {
        for (String line : block.split("\\r?\\n")) {
            String value = line == null ? "" : line.trim();
            if (value.startsWith(prefix)) {
                return value.substring(prefix.length()).trim();
            }
        }
        return "";
    }

    private static List<String> collectContextLines(String text, int limit) {
        List<String> lines = new ArrayList<>();
        if (text == null) {
            return lines;
        }

        String[] raw = text.split("\\r?\\n");
        for (String s : raw) {
            String t = s == null ? "" : s.trim();
            if (t.isEmpty() || t.matches("^=+\\s*第\\d+页\\s*=+$")) {
                continue;
            }
            if (t.length() > 120) {
                t = t.substring(0, 120);
            }
            lines.add(t);
            if (lines.size() >= limit) {
                break;
            }
        }
        return lines;
    }
}
