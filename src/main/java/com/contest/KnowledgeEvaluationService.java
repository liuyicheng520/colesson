package com.contest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
public class KnowledgeEvaluationService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final KnowledgeRepository repository;
    private final KnowledgeRetrievalService retrievalService;

    public KnowledgeEvaluationService(
            KnowledgeRepository repository,
            KnowledgeRetrievalService retrievalService
    ) {
        this.repository = repository;
        this.retrievalService = retrievalService;
    }

    public Map<String, Object> run() throws Exception {
        List<KnowledgeRepository.EvaluationCase> cases = repository.loadEvaluationCases();
        List<Map<String, Object>> rows = new ArrayList<>();
        int passed = 0;

        for (KnowledgeRepository.EvaluationCase item : cases) {
            List<KnowledgeRetrievalService.Hit> hits = retrievalService.search(
                    item.courseCode(), item.question(), item.topK()
            );
            String joined = hits.stream()
                    .map(hit -> hit.candidate().content() + " " + hit.candidate().sectionTitle())
                    .reduce("", (left, right) -> left + "\n" + right)
                    .toLowerCase(Locale.ROOT);
            JsonNode expected = objectMapper.readTree(item.expectedKeywords());
            List<String> matched = new ArrayList<>();
            for (JsonNode keyword : expected) {
                String value = keyword.asText("").trim();
                if (!value.isBlank() && joined.contains(value.toLowerCase(Locale.ROOT))) {
                    matched.add(value);
                }
            }
            boolean sourceMatched = item.expectedSourceUrl() == null || item.expectedSourceUrl().isBlank()
                    || hits.stream().anyMatch(hit -> item.expectedSourceUrl().equals(hit.candidate().sourceUrl()));
            boolean casePassed = sourceMatched && !matched.isEmpty();
            if (casePassed) {
                passed++;
            }
            KnowledgeRetrievalService.Hit top = hits.isEmpty() ? null : hits.get(0);
            repository.insertEvaluationRun(
                    "run_" + UUID.randomUUID().toString().replace("-", ""),
                    item.id(),
                    casePassed,
                    String.join(",", matched),
                    top == null ? "" : top.candidate().documentId(),
                    top == null ? 0 : top.score(),
                    "retrieved=" + hits.size() + ", sourceMatched=" + sourceMatched
                            + ", expected=" + item.expectedKeywords()
            );

            Map<String, Object> row = new LinkedHashMap<>();
            row.put("caseId", item.id());
            row.put("courseCode", item.courseCode());
            row.put("questionType", item.questionType());
            row.put("question", item.question());
            row.put("passed", casePassed);
            row.put("sourceMatched", sourceMatched);
            row.put("matchedKeywords", matched);
            row.put("topScore", top == null ? 0 : top.score());
            row.put("topSource", top == null ? "" : top.candidate().sourceUrl());
            rows.add(row);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("caseCount", cases.size());
        result.put("passedCount", passed);
        result.put("passRate", cases.isEmpty() ? 0 : Math.round(passed * 10000.0 / cases.size()) / 100.0);
        result.put("items", rows);
        return result;
    }
}
