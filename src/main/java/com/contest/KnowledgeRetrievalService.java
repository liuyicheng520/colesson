package com.contest;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class KnowledgeRetrievalService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeRetrievalService.class);
    private static final Pattern LATIN_TOKEN = Pattern.compile("[a-z0-9_.$-]{2,}");
    private static final Pattern CJK_SEQUENCE = Pattern.compile("[\\p{IsHan}]{2,}");

    private final KnowledgeRepository repository;

    public KnowledgeRetrievalService(KnowledgeRepository repository) {
        this.repository = repository;
    }

    public List<Hit> search(String projectCourseCode, String question, int topK) {
        String courseCode = normalizeCourseCode(projectCourseCode);
        if (question == null || question.isBlank() || courseCode.isBlank()) {
            return List.of();
        }
        try {
            List<KnowledgeRepository.Candidate> candidates = repository.loadCandidates(courseCode, 8000);
            return rank(candidates, question, topK);
        } catch (SQLException e) {
            log.warn("计算机课程知识库暂不可用，继续使用项目资料回答: {}", e.getMessage());
            return List.of();
        }
    }

    public List<Hit> rank(List<KnowledgeRepository.Candidate> candidates, String question, int topK) {
        String query = normalize(question);
        Set<String> queryTokens = tokens(query);
        expandSemanticTokens(query, queryTokens);
        List<Hit> hits = new ArrayList<>();
        for (KnowledgeRepository.Candidate item : candidates) {
            String titleText = normalize(
                    nullToEmpty(item.documentTitle()) + " "
                            + nullToEmpty(item.sectionTitle()) + " "
                            + nullToEmpty(item.chunkType())
            );
            String bodyText = normalize(nullToEmpty(item.searchText()) + " " + nullToEmpty(item.content()));
            Set<String> bodyTokens = tokens(bodyText);
            double score = similarity(query, queryTokens, titleText, bodyText, bodyTokens);
            if (score <= 0) {
                continue;
            }
            double qualityWeight = 0.65 + Math.max(0, Math.min(100, item.qualityScore())) / 100.0 * 0.35;
            hits.add(new Hit(item, Math.round(score * qualityWeight * 100.0) / 100.0));
        }
        hits.sort(Comparator.comparingDouble(Hit::score).reversed());
        return hits.subList(0, Math.min(Math.max(1, topK), hits.size()));
    }

    public String formatContext(List<Hit> hits) {
        if (hits == null || hits.isEmpty()) {
            return "";
        }
        StringBuilder context = new StringBuilder();
        for (int i = 0; i < hits.size(); i++) {
            Hit hit = hits.get(i);
            KnowledgeRepository.Candidate item = hit.candidate();
            context.append("\n【知识片段 ").append(i + 1).append("】")
                    .append("\n课程：").append(item.courseCode())
                    .append("\n文档：").append(item.documentTitle())
                    .append("\n章节：").append(nullToEmpty(item.sectionTitle()))
                    .append("\n来源：").append(item.sourceUrl())
                    .append("\n版本：").append(nullToEmpty(item.versionLabel()))
                    .append("\n许可证：").append(nullToEmpty(item.licenseName()))
                    .append("\n质量等级：").append(nullToEmpty(item.qualityTier()))
                    .append("（").append(item.qualityScore()).append("）")
                    .append("\n内容：\n").append(item.content()).append('\n');
        }
        return context.length() > 9000 ? context.substring(0, 9000) : context.toString();
    }

    public List<Map<String, Object>> sourceViews(List<Hit> hits) {
        List<Map<String, Object>> sources = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (Hit hit : hits) {
            KnowledgeRepository.Candidate item = hit.candidate();
            if (!seen.add(item.documentId())) {
                continue;
            }
            Map<String, Object> source = new LinkedHashMap<>();
            source.put("documentId", item.documentId());
            source.put("title", item.documentTitle());
            source.put("section", item.sectionTitle());
            source.put("url", item.sourceUrl());
            source.put("publisher", item.publisher());
            source.put("version", item.versionLabel());
            source.put("license", item.licenseName());
            source.put("licenseUrl", item.licenseUrl());
            source.put("qualityTier", item.qualityTier());
            source.put("qualityScore", item.qualityScore());
            source.put("sourceUpdatedAt", item.sourceUpdatedAt());
            source.put("retrievalScore", hit.score());
            sources.add(source);
        }
        return sources;
    }

    public String normalizeCourseCode(String value) {
        String course = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        return switch (course) {
            case "java_web", "java", "java_se" -> "java";
            case "database", "database_principles", "sql" -> "database";
            case "data_structure", "data_structures", "algorithm" -> "data_structure";
            case "computer_network", "network" -> "computer_network";
            case "operating_system", "os" -> "operating_system";
            default -> course;
        };
    }

    private double similarity(
            String query,
            Set<String> queryTokens,
            String titleText,
            String bodyText,
            Set<String> bodyTokens
    ) {
        double score = 0;
        if (bodyText.contains(query)) {
            score += 45;
        }
        if (titleText.contains(query)) {
            score += 35;
        }
        int overlap = 0;
        for (String token : queryTokens) {
            if (bodyTokens.contains(token)) {
                overlap++;
            }
            if (titleText.contains(token)) {
                score += 4;
            }
        }
        for (String semanticToken : List.of("containskey", "getordefault")) {
            if (queryTokens.contains(semanticToken)
                    && (bodyText.contains(semanticToken) || titleText.contains(semanticToken))) {
                score += 28;
            }
        }
        if (!queryTokens.isEmpty() && !bodyTokens.isEmpty() && overlap > 0) {
            score += overlap / Math.sqrt((double) queryTokens.size() * bodyTokens.size()) * 70.0;
            score += overlap * 2.5;
        }
        return score;
    }

    private Set<String> tokens(String text) {
        Set<String> result = new HashSet<>();
        Matcher latin = LATIN_TOKEN.matcher(text);
        while (latin.find()) {
            result.add(latin.group());
        }
        Matcher cjk = CJK_SEQUENCE.matcher(text);
        while (cjk.find()) {
            String value = cjk.group();
            if (value.length() <= 4) {
                result.add(value);
            }
            for (int i = 0; i < value.length() - 1; i++) {
                result.add(value.substring(i, i + 2));
            }
        }
        return result;
    }

    private void expandSemanticTokens(String query, Set<String> tokens) {
        if ((query.contains("键不存在") || query.contains("键是否存在") || query.contains("包含键"))
                && query.contains("null")) {
            tokens.add("containskey");
        }
        if (query.contains("默认值")) {
            tokens.add("getordefault");
        }
    }

    private String normalize(String value) {
        return nullToEmpty(value).toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9_.$\\-\\p{IsHan}]+", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    public record Hit(KnowledgeRepository.Candidate candidate, double score) {
    }
}
