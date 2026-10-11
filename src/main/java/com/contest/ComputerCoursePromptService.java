package com.contest;

import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class ComputerCoursePromptService {

    private static final Pattern ERROR_TYPE = Pattern.compile(
            "([\\w.$]+(?:Exception|Error))|(?:错误|异常)[：:]?\\s*([^\\r\\n，。]+)"
    );

    public String generateLectureScript(
            ProjectService.ProjectRecord project,
            String pptText,
            String resourceContext
    ) {
        return AiApiUtil.generateComputerLectureScript(
                project == null ? "" : project.getCourseType(),
                project == null ? "" : project.getProgrammingLanguage(),
                project == null ? "" : project.getTeachingGoal(),
                pptText,
                resourceContext
        );
    }

    public Map<String, String> answer(
            ProjectService.ProjectRecord project,
            String questionType,
            String question,
            String pptText,
            String resourceContext,
            String knowledgeContext,
            String preferredResourceId
    ) {
        String normalizedType = classifyQuestionType(questionType, question);
        String answer = AiApiUtil.answerComputerQuestion(
                project == null ? "" : project.getCourseType(),
                project == null ? "" : project.getProgrammingLanguage(),
                normalizedType,
                question,
                pptText,
                resourceContext,
                knowledgeContext
        );

        Map<String, String> result = new LinkedHashMap<>();
        result.put("answer", answer);
        result.put("questionType", normalizedType);
        result.put("resourceId", preferredResourceId == null ? "" : preferredResourceId);
        result.put("errorType", "debug".equals(normalizedType) ? detectErrorType(question + "\n" + resourceContext) : "");
        result.put("hintLevel", "debug".equals(normalizedType) ? "1" : "0");
        result.put("sourceLabel", sourceLabel(pptText, resourceContext, knowledgeContext));
        return result;
    }

    public String classifyQuestionType(String requested, String question) {
        String value = requested == null ? "" : requested.trim().toLowerCase(Locale.ROOT);
        if ("concept".equals(value) || "code".equals(value) || "debug".equals(value)) {
            return value;
        }
        String text = question == null ? "" : question.toLowerCase(Locale.ROOT);
        if (text.contains("exception") || text.contains("error") || text.contains("报错")
                || text.contains("异常") || text.contains("为什么运行不了")) {
            return "debug";
        }
        if (text.contains("代码") || text.contains("方法") || text.contains("类")
                || text.contains("sql") || text.contains("函数")) {
            return "code";
        }
        return "concept";
    }

    public String detectErrorType(String text) {
        Matcher matcher = ERROR_TYPE.matcher(text == null ? "" : text);
        if (matcher.find()) {
            String value = matcher.group(1) != null ? matcher.group(1) : matcher.group(2);
            return value == null ? "待进一步定位" : value.trim();
        }
        return "待进一步定位";
    }

    private String sourceLabel(String pptText, String resourceContext, String knowledgeContext) {
        boolean hasPpt = pptText != null && !pptText.isBlank()
                && !"课堂问答上下文".equals(pptText.trim());
        boolean hasResource = resourceContext != null && !resourceContext.isBlank();
        boolean hasKnowledge = knowledgeContext != null && !knowledgeContext.isBlank();
        if (hasPpt && hasResource && hasKnowledge) return "当前课件 + 项目资料 + 课程知识库";
        if (hasResource && hasKnowledge) return "当前项目资料 + 课程知识库";
        if (hasPpt && hasKnowledge) return "当前课件 + 课程知识库";
        if (hasKnowledge) return "课程知识库";
        if (hasPpt && hasResource) return "当前课件 + 当前项目代码/实验资料";
        if (hasResource) return "当前项目代码/实验资料";
        return "当前课程课件";
    }
}
