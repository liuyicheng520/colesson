package com.contest;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 教师端「教学讲稿」→ 学生端同款沉浸式讲解视频数据结构。
 * 讲稿是独立口播稿；PPT 只作页标题/知识点锚点，禁止把课件原文当旁白或要点。
 */
public final class TeacherLectureVideoUtil {

    private static final ObjectMapper MAPPER = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);
    private static final Pattern PAGE_HEADER = Pattern.compile("^===\\s*第(\\d+)页\\s*===$");
    private static final Pattern SCRIPT_PAGE_HEADER = Pattern.compile(
            "(?m)^(?:===\\s*)?第\\s*(\\d+)\\s*页(?:\\s*===)?[^\\n]*$"
    );
    private static final Pattern QUIZ_BLOCK = Pattern.compile(
            "【互动题】\\s*([\\s\\S]*?)(?=【互动题】|===\\s*第\\d+页===|第\\s*\\d+\\s*页|$)"
    );
    private static final Pattern OPTION_LINE = Pattern.compile("(?m)^\\s*([A-D])[.、:：)\\s]\\s*(.+)$");
    private static final Pattern ANSWER_LINE = Pattern.compile("(?m)^\\s*答案\\s*[:：]\\s*([A-D])");
    private static final Pattern ANALYSIS_LINE = Pattern.compile("(?m)^\\s*解析\\s*[:：]\\s*(.+)$");
    private static final Pattern QUESTION_LINE = Pattern.compile("(?m)^\\s*(?:问|题目)?\\s*[:：]?\\s*(.+)$");

    private TeacherLectureVideoUtil() {
    }

    public static Map<String, Object> buildLecture(
            String lectureId,
            String topic,
            String pptRawText,
            String script
    ) {
        String safeTopic = (topic == null || topic.trim().isEmpty()) ? "课程讲解" : topic.trim();
        String safeLectureId = (lectureId == null || lectureId.trim().isEmpty())
                ? ("host-" + System.currentTimeMillis())
                : lectureId.trim();
        String teachScript = script == null ? "" : script.trim();

        List<SlideSource> pptPages = extractPages(pptRawText);
        Map<Integer, String> scriptByPage = splitScriptByPage(teachScript);
        List<QuizDraft> quizzesFromScript = extractQuizzes(teachScript);

        List<Map<String, Object>> slides = new ArrayList<>();
        int slideId = 1;

        if (!scriptByPage.isEmpty()) {
            List<Integer> pageNos = new ArrayList<>(scriptByPage.keySet());
            pageNos.sort(Integer::compareTo);
            for (int idx = 0; idx < pageNos.size(); idx++) {
                int pageNo = pageNos.get(idx);
                String narration = expandTeachingNarration(scriptByPage.get(pageNo), safeTopic, pageNo);
                SlideSource ppt = findPage(pptPages, pageNo);
                String title = resolveTitle(ppt, narration, pageNo, safeTopic);
                slides.add(contentSlide(slideId++, title, teachingBullets(narration, ppt), narration));

                // 每隔约 3 页插入一道互动题（优先用讲稿中的互动题）
                if ((idx + 1) % 3 == 0) {
                    QuizDraft quiz = takeQuiz(quizzesFromScript, title, narration);
                    slides.add(quizSlide(slideId++, quiz));
                }
            }
        } else if (!pptPages.isEmpty() && !teachScript.isEmpty()) {
            // 有讲稿但无分页标记：按页均分讲稿，绝不使用 PPT 原文作旁白
            List<String> chunks = splitScriptIntoChunks(teachScript, pptPages.size());
            for (int i = 0; i < pptPages.size(); i++) {
                SlideSource ppt = pptPages.get(i);
                String narration = expandTeachingNarration(
                        i < chunks.size() ? chunks.get(i) : "",
                        safeTopic,
                        ppt.page
                );
                String title = resolveTitle(ppt, narration, ppt.page, safeTopic);
                slides.add(contentSlide(slideId++, title, teachingBullets(narration, ppt), narration));
                if ((i + 1) % 3 == 0) {
                    slides.add(quizSlide(slideId++, takeQuiz(quizzesFromScript, title, narration)));
                }
            }
        } else if (!teachScript.isEmpty()) {
            List<String> chunks = splitScriptIntoChunks(teachScript, Math.max(3, estimateChunkCount(teachScript)));
            for (int i = 0; i < chunks.size(); i++) {
                String narration = expandTeachingNarration(chunks.get(i), safeTopic, i + 1);
                String title = firstSentence(narration, "第" + (i + 1) + "段讲解");
                slides.add(contentSlide(slideId++, title, teachingBullets(narration, null), narration));
                if ((i + 1) % 3 == 0) {
                    slides.add(quizSlide(slideId++, takeQuiz(quizzesFromScript, title, narration)));
                }
            }
        } else {
            // 无讲稿时也不复读 PPT：生成引导性教学旁白
            if (pptPages.isEmpty()) {
                String narration = "同学们好，下面我们开始今天的课程《" + safeTopic + "》。"
                        + "请先带着问题听讲：这一节要解决什么问题？学完后你能用自己的话讲清楚吗？";
                slides.add(contentSlide(slideId++, safeTopic, List.of(
                        "带着问题听讲，而不是背课件标题",
                        "先抓「解决什么问题」",
                        "再用自己的话复述核心结论"
                ), narration));
            } else {
                for (int i = 0; i < pptPages.size(); i++) {
                    SlideSource ppt = pptPages.get(i);
                    String title = ppt.lines.isEmpty() ? ("第" + ppt.page + "页") : trimTo(ppt.lines.get(0), 80);
                    String narration = synthesizeFromOutline(title, ppt.lines, safeTopic, ppt.page);
                    slides.add(contentSlide(slideId++, title, teachingBullets(narration, ppt), narration));
                    if ((i + 1) % 3 == 0) {
                        slides.add(quizSlide(slideId++, takeQuiz(quizzesFromScript, title, narration)));
                    }
                }
            }
        }

        // 讲稿里剩余互动题追加到末尾
        while (!quizzesFromScript.isEmpty()) {
            slides.add(quizSlide(slideId++, quizzesFromScript.remove(0)));
        }

        // 至少保证有一道互动题
        long quizCount = slides.stream().filter(s -> "quiz".equals(s.get("type"))).count();
        if (quizCount == 0 && !slides.isEmpty()) {
            Map<String, Object> lastContent = null;
            for (int i = slides.size() - 1; i >= 0; i--) {
                if ("content".equals(slides.get(i).get("type"))) {
                    lastContent = slides.get(i);
                    break;
                }
            }
            String anchor = lastContent == null ? safeTopic : String.valueOf(lastContent.get("title"));
            String narr = lastContent == null ? safeTopic : String.valueOf(lastContent.get("narration"));
            slides.add(quizSlide(slideId, takeQuiz(new ArrayList<>(), anchor, narr)));
        }

        long contentCount = slides.stream().filter(s -> "content".equals(s.get("type"))).count();
        long finalQuizCount = slides.stream().filter(s -> "quiz".equals(s.get("type"))).count();

        Map<String, Object> lecture = new HashMap<>();
        lecture.put("lecture_id", safeLectureId);
        lecture.put("topic", safeTopic);
        lecture.put("slides", slides);
        lecture.put("content_slide_count", contentCount);
        lecture.put("quiz_count", finalQuizCount);
        lecture.put("recommendations", defaultRecommendations(safeTopic));
        lecture.put("created_at", Instant.now().toString());
        lecture.put("source", "teacher_host");
        return lecture;
    }

    public static Path writeLectureFile(Path root, String lectureId, Map<String, Object> lecture) throws Exception {
        Path dir = root.resolve("lectures");
        Files.createDirectories(dir);
        Path file = dir.resolve(lectureId + ".json");
        Files.write(file, MAPPER.writeValueAsBytes(lecture));
        return file;
    }

    public static Map<String, Object> readLectureFile(Path root, String lectureId) throws Exception {
        if (lectureId == null || lectureId.trim().isEmpty()) {
            return null;
        }
        Path file = root.resolve("lectures").resolve(lectureId.trim() + ".json");
        if (!Files.isRegularFile(file)) {
            return null;
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> lecture = MAPPER.readValue(Files.readAllBytes(file), Map.class);
        return lecture;
    }

    public static String openUrl(String lectureId, String projectId) {
        StringBuilder sb = new StringBuilder();
        sb.append("/student/tutor/lecture/").append(lectureId);
        sb.append("?from=host");
        if (projectId != null && !projectId.trim().isEmpty()) {
            sb.append("&projectId=").append(projectId.trim());
        }
        return sb.toString();
    }

    private static Map<String, Object> contentSlide(int id, String title, List<String> bullets, String narration) {
        Map<String, Object> slide = new LinkedHashMap<>();
        slide.put("id", id);
        slide.put("type", "content");
        slide.put("title", title);
        slide.put("bullets", bullets);
        slide.put("narration", narration);
        return slide;
    }

    private static Map<String, Object> quizSlide(int id, QuizDraft quiz) {
        Map<String, Object> slide = new LinkedHashMap<>();
        slide.put("id", id);
        slide.put("type", "quiz");
        slide.put("title", "随堂测验");
        slide.put("question", quiz.question);
        slide.put("options", quiz.options);
        slide.put("answer", quiz.answer);
        slide.put("multi", false);
        slide.put("analysis", quiz.analysis);
        slide.put("narration", "请先暂停思考一下：" + quiz.question + " 选好后提交，我们再继续讲解。");
        return slide;
    }

    private static QuizDraft takeQuiz(List<QuizDraft> pool, String title, String narration) {
        if (pool != null && !pool.isEmpty()) {
            return pool.remove(0);
        }
        return autoQuiz(title, narration);
    }

    private static QuizDraft autoQuiz(String title, String narration) {
        String topic = trimTo(title == null || title.isBlank() ? "本节要点" : title, 40);
        String hint = firstSentence(narration, topic);
        QuizDraft q = new QuizDraft();
        q.question = "学完「" + topic + "」后，下面哪一项最符合老师强调的学习目标？";
        q.options = List.of(
                "A. 能用自己的话解释它解决什么问题、为什么重要",
                "B. 只需背下课件上的原句即可",
                "C. 不需要联系前后知识，单独记忆即可",
                "D. 只要会做题，不必理解概念"
        );
        q.answer = "A";
        q.analysis = "课堂目标不是复述课件原文，而是形成可迁移的理解。参考提示：" + trimTo(hint, 80);
        return q;
    }

    private static List<QuizDraft> extractQuizzes(String script) {
        List<QuizDraft> list = new ArrayList<>();
        if (script == null || script.isBlank()) {
            return list;
        }
        Matcher m = QUIZ_BLOCK.matcher(script);
        while (m.find()) {
            QuizDraft q = parseQuizBody(m.group(1));
            if (q != null) {
                list.add(q);
            }
        }
        return list;
    }

    private static QuizDraft parseQuizBody(String body) {
        if (body == null || body.isBlank()) {
            return null;
        }
        String text = body.trim();
        List<String> options = new ArrayList<>();
        Matcher om = OPTION_LINE.matcher(text);
        while (om.find()) {
            options.add(om.group(1).toUpperCase() + ". " + om.group(2).trim());
        }
        if (options.size() < 2) {
            return null;
        }
        String answer = "A";
        Matcher am = ANSWER_LINE.matcher(text);
        if (am.find()) {
            answer = am.group(1).toUpperCase();
        }
        String analysis = "结合刚才的讲解，对照概念再想一遍为什么。";
        Matcher xm = ANALYSIS_LINE.matcher(text);
        if (xm.find()) {
            analysis = xm.group(1).trim();
        }
        String question = null;
        for (String line : text.split("\\r?\\n")) {
            String t = line.trim();
            if (t.isEmpty() || t.startsWith("A.") || t.startsWith("B.") || t.startsWith("C.") || t.startsWith("D.")
                    || t.startsWith("答案") || t.startsWith("解析") || OPTION_LINE.matcher(t).matches()) {
                continue;
            }
            Matcher qm = QUESTION_LINE.matcher(t);
            if (qm.find()) {
                question = qm.group(1).trim();
                break;
            }
            question = t;
            break;
        }
        if (question == null || question.isBlank()) {
            return null;
        }
        QuizDraft q = new QuizDraft();
        q.question = question;
        q.options = options;
        q.answer = answer;
        q.analysis = analysis;
        return q;
    }

    private static List<String> teachingBullets(String narration, SlideSource ppt) {
        List<String> bullets = new ArrayList<>();
        // 优先从口播稿抽「教学要点」，避免直接贴 PPT 条目
        for (String part : narration.split("[。！？!?]")) {
            String t = part == null ? "" : part.trim();
            if (t.length() < 8) {
                continue;
            }
            if (t.startsWith("同学们") || t.startsWith("下面我们") || t.startsWith("接下来")
                    || t.startsWith("好，") || t.startsWith("那么")) {
                continue;
            }
            if (t.contains("想一想") || t.contains("请大家") || t.contains("互动") || t.contains("提问")) {
                bullets.add(trimTo("💭 " + t.replaceFirst("^[:：\\s]+", ""), 72));
            } else if (t.contains("注意") || t.contains("关键") || t.contains("重点") || t.contains("核心")) {
                bullets.add(trimTo("★ " + t, 72));
            } else if (bullets.size() < 2) {
                bullets.add(trimTo(t, 72));
            }
            if (bullets.size() >= 5) {
                break;
            }
        }
        if (bullets.isEmpty()) {
            bullets.add("听懂「是什么」还不够，还要能说清「为什么」");
            bullets.add("用自己的例子检验是否真正理解");
            if (ppt != null && !ppt.lines.isEmpty()) {
                bullets.add("本页知识点锚点：" + trimTo(ppt.lines.get(0), 40));
            }
        }
        return bullets;
    }

    private static String expandTeachingNarration(String raw, String topic, int pageNo) {
        String text = raw == null ? "" : raw.trim();
        // 去掉讲稿中的互动题块，避免朗读选项
        text = QUIZ_BLOCK.matcher(text).replaceAll("").trim();
        if (text.isEmpty()) {
            return "同学们，我们来看第" + pageNo + "部分关于《" + topic + "》的内容。"
                    + "请不要只盯着课件标题，先想一想：它要解决什么问题？"
                    + "听完后，试着用自己的话讲给同桌听。";
        }
        // 若几乎像条目罗列（很短且无口语），补教学引导
        if (text.length() < 40 || looksLikeOutlineOnly(text)) {
            return "同学们，关于「" + firstSentence(text, topic) + "」，我们不要照着念。"
                    + "老师换个讲法：" + text
                    + " 大家想一想，如果把它放到实际学习或项目里，你会怎么用？为什么这样用？";
        }
        if (!text.contains("想一想") && !text.contains("请大家") && text.length() > 60) {
            text = text + " 大家可以先停三秒想一想：刚才这一点，你能用自己的话复述吗？";
        }
        return text;
    }

    private static String synthesizeFromOutline(String title, List<String> lines, String topic, int pageNo) {
        StringBuilder sb = new StringBuilder();
        sb.append("同学们，我们进入第").append(pageNo).append("部分：").append(title).append("。");
        sb.append("课件上只是提纲，老师讲的时候会展开。");
        int n = 0;
        for (int i = 1; i < lines.size() && n < 4; i++) {
            String point = lines.get(i).trim();
            if (point.isEmpty() || point.equals(title)) {
                continue;
            }
            n++;
            sb.append("第").append(n).append("点，").append(point).append("。");
            sb.append("关键不是背这句话，而是弄清它解决什么问题、和前后知识怎么衔接。");
        }
        if (n == 0) {
            sb.append("请抓住主题《").append(topic).append("》，先问自己：学完这一页，我能向同学讲清楚吗？");
        } else {
            sb.append("大家想一想：如果只记住标题，考试或实践时会不会卡住？所以请跟着老师的例子理解。");
        }
        return sb.toString();
    }

    private static boolean looksLikeOutlineOnly(String text) {
        String[] parts = text.split("[。；;\\n]");
        int shortParts = 0;
        for (String p : parts) {
            if (p.trim().length() > 0 && p.trim().length() <= 18) {
                shortParts++;
            }
        }
        return shortParts >= 2 && text.length() < 120;
    }

    private static String resolveTitle(SlideSource ppt, String narration, int pageNo, String topic) {
        if (ppt != null && !ppt.lines.isEmpty()) {
            return trimTo(ppt.lines.get(0), 80);
        }
        return firstSentence(narration, "第" + pageNo + "页 · " + topic);
    }

    private static SlideSource findPage(List<SlideSource> pages, int pageNo) {
        for (SlideSource p : pages) {
            if (p.page == pageNo) {
                return p;
            }
        }
        if (pageNo >= 1 && pageNo <= pages.size()) {
            return pages.get(pageNo - 1);
        }
        return null;
    }

    private static List<String> defaultRecommendations(String topic) {
        List<String> list = new ArrayList<>();
        list.add("用自己的话复述《" + trimTo(topic, 20) + "》的核心问题与结论");
        list.add("挑一个生活或项目例子，解释今天最重要的一个概念");
        list.add("把互动题错因记进笔记，下次讲解前先自测一遍");
        return list;
    }

    private static List<SlideSource> extractPages(String rawText) {
        List<SlideSource> result = new ArrayList<>();
        if (rawText == null || rawText.trim().isEmpty()) {
            return result;
        }
        SlideSource current = null;
        for (String row : rawText.split("\\r?\\n")) {
            String line = row == null ? "" : row.trim();
            Matcher m = PAGE_HEADER.matcher(line);
            if (m.matches()) {
                if (current != null) {
                    result.add(current);
                }
                current = new SlideSource(Integer.parseInt(m.group(1)));
            } else if (current != null && !line.isEmpty()) {
                current.lines.add(line);
            }
        }
        if (current != null) {
            result.add(current);
        }
        return result;
    }

    private static Map<Integer, String> splitScriptByPage(String script) {
        Map<Integer, String> map = new LinkedHashMap<>();
        if (script == null || script.trim().isEmpty()) {
            return map;
        }
        Matcher m = SCRIPT_PAGE_HEADER.matcher(script);
        List<int[]> marks = new ArrayList<>();
        while (m.find()) {
            marks.add(new int[]{Integer.parseInt(m.group(1)), m.start(), m.end()});
        }
        if (marks.isEmpty()) {
            return map;
        }
        for (int i = 0; i < marks.size(); i++) {
            int page = marks.get(i)[0];
            int contentStart = marks.get(i)[2];
            int contentEnd = i + 1 < marks.size() ? marks.get(i + 1)[1] : script.length();
            String body = script.substring(contentStart, contentEnd).trim();
            if (!body.isEmpty()) {
                map.put(page, body);
            }
        }
        return map;
    }

    private static List<String> splitScriptIntoChunks(String script, int parts) {
        List<String> chunks = new ArrayList<>();
        if (script == null || script.isBlank() || parts <= 1) {
            chunks.add(script == null ? "" : script.trim());
            return chunks;
        }
        String cleaned = QUIZ_BLOCK.matcher(script).replaceAll("\n").trim();
        String[] paras = cleaned.split("\\n\\s*\\n");
        List<String> units = new ArrayList<>();
        for (String p : paras) {
            String t = p.trim();
            if (!t.isEmpty()) {
                units.add(t);
            }
        }
        if (units.size() < parts) {
            // 按句再切
            units.clear();
            for (String sentence : cleaned.split("(?<=[。！？])")) {
                String t = sentence.trim();
                if (!t.isEmpty()) {
                    units.add(t);
                }
            }
        }
        if (units.isEmpty()) {
            chunks.add(cleaned);
            return chunks;
        }
        int per = Math.max(1, (int) Math.ceil(units.size() / (double) parts));
        for (int i = 0; i < units.size(); i += per) {
            StringBuilder sb = new StringBuilder();
            for (int j = i; j < Math.min(units.size(), i + per); j++) {
                if (sb.length() > 0) {
                    sb.append('\n');
                }
                sb.append(units.get(j));
            }
            chunks.add(sb.toString());
            if (chunks.size() >= parts) {
                // 剩余并入最后一块
                if (i + per < units.size()) {
                    StringBuilder rest = new StringBuilder(chunks.get(chunks.size() - 1));
                    for (int j = i + per; j < units.size(); j++) {
                        rest.append('\n').append(units.get(j));
                    }
                    chunks.set(chunks.size() - 1, rest.toString());
                }
                break;
            }
        }
        while (chunks.size() < parts) {
            chunks.add(chunks.get(chunks.size() - 1));
        }
        return chunks;
    }

    private static int estimateChunkCount(String script) {
        int len = script == null ? 0 : script.length();
        return Math.min(12, Math.max(3, len / 280));
    }

    private static String firstSentence(String text, String fallback) {
        if (text == null || text.isBlank()) {
            return fallback;
        }
        String t = text.trim().replaceAll("\\s+", " ");
        int cut = -1;
        for (char c : new char[]{'。', '！', '？', '.', '!', '?'}) {
            int i = t.indexOf(c);
            if (i > 0 && (cut < 0 || i < cut)) {
                cut = i;
            }
        }
        if (cut > 0) {
            return trimTo(t.substring(0, cut), 80);
        }
        return trimTo(t, 80);
    }

    private static String trimTo(String text, int max) {
        String t = text == null ? "" : text.trim();
        if (t.length() <= max) {
            return t;
        }
        return t.substring(0, max) + "…";
    }

    private static final class SlideSource {
        final int page;
        final List<String> lines = new ArrayList<>();

        SlideSource(int page) {
            this.page = page;
        }
    }

    private static final class QuizDraft {
        String question;
        List<String> options = new ArrayList<>();
        String answer = "A";
        String analysis = "";
    }
}
