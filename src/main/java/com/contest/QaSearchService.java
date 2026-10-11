package com.contest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class QaSearchService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private volatile List<QaItem> qaItems = Collections.emptyList();

    @PostConstruct
    public void init() {
        loadDataset();
    }

    public List<Map<String, Object>> search(String question, int topK) {
        if (question == null || question.trim().isEmpty()) {
            return Collections.emptyList();
        }

        String query = question.trim();
        String queryNorm = normalize(query);
        Set<String> queryTokens = tokens(queryNorm);

        List<SearchHit> hits = new ArrayList<>();
        for (QaItem item : qaItems) {
            double bestScore = 0.0;
            String bestMatch = item.question;

            for (String candidate : item.searchTexts) {
                double score = score(query, queryNorm, queryTokens, candidate);
                if (score > bestScore) {
                    bestScore = score;
                    bestMatch = candidate;
                }
            }

            if (bestScore > 0) {
                hits.add(new SearchHit(item, bestScore, bestMatch));
            }
        }

        hits.sort(Comparator.comparingDouble(SearchHit::getScore).reversed());

        int limit = Math.min(Math.max(topK, 1), 20);
        List<Map<String, Object>> result = new ArrayList<>();

        for (int i = 0; i < Math.min(limit, hits.size()); i++) {
            SearchHit hit = hits.get(i);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", hit.item.id);
            row.put("category", hit.item.category);
            row.put("question", hit.item.question);
            row.put("answer", hit.item.answer);
            row.put("matchedText", hit.bestMatch);
            row.put("score", Math.round(hit.score * 100.0) / 100.0);
            result.add(row);
        }

        return result;
    }

    private void loadDataset() {
        ClassPathResource resource = new ClassPathResource("data/qa_dataset.jsonl");
        if (!resource.exists()) {
            System.err.println("⚠️ 未找到 data/qa_dataset.jsonl，TopK检索接口将返回空结果。");
            qaItems = Collections.emptyList();
            return;
        }

        List<QaItem> loaded = new ArrayList<>();

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.trim().isEmpty()) {
                    continue;
                }
                JsonNode node = objectMapper.readTree(line);

                String question = text(node, "question");
                String answer = text(node, "answer");
                if (question.isEmpty() || answer.isEmpty()) {
                    continue;
                }

                QaItem item = new QaItem();
                item.id = node.path("id").asInt();
                item.category = text(node, "category");
                item.question = question;
                item.answer = answer;

                item.searchTexts.add(item.question);
                if (!item.category.isEmpty()) {
                    item.searchTexts.add(item.category + " " + item.question);
                }

                JsonNode syn = node.path("synonyms");
                if (syn.isArray()) {
                    for (JsonNode s : syn) {
                        String text = s.asText("").trim();
                        if (!text.isEmpty()) {
                            item.searchTexts.add(text);
                        }
                    }
                }

                loaded.add(item);
            }
        } catch (Exception e) {
            e.printStackTrace();
            qaItems = Collections.emptyList();
            return;
        }

        qaItems = loaded;
        System.out.println("✅ QA检索数据已加载：" + loaded.size() + " 条");
    }

    private String text(JsonNode node, String field) {
        return node.path(field).asText("").trim();
    }

    private double score(String rawQuery, String queryNorm, Set<String> queryTokens, String candidate) {
        if (candidate == null || candidate.trim().isEmpty()) {
            return 0;
        }

        String candRaw = candidate.trim();
        String candNorm = normalize(candRaw);
        if (candNorm.isEmpty()) {
            return 0;
        }

        double score = 0;

        if (rawQuery.equalsIgnoreCase(candRaw)) {
            score += 100;
        }

        if (candNorm.equals(queryNorm)) {
            score += 90;
        } else if (candNorm.contains(queryNorm) || queryNorm.contains(candNorm)) {
            score += 35;
        }

        Set<String> candTokens = tokens(candNorm);
        if (!queryTokens.isEmpty() && !candTokens.isEmpty()) {
            int overlap = 0;
            for (String t : queryTokens) {
                if (candTokens.contains(t)) {
                    overlap++;
                }
            }

            if (overlap > 0) {
                double cosineLike = overlap / Math.sqrt((double) queryTokens.size() * candTokens.size());
                score += cosineLike * 60.0;
            }
        }

        if (score == 0 && charOverlap(queryNorm, candNorm) > 0.45) {
            score = 15;
        }

        return score;
    }

    private double charOverlap(String a, String b) {
        String x = a.replace(" ", "");
        String y = b.replace(" ", "");
        if (x.isEmpty() || y.isEmpty()) {
            return 0;
        }

        Set<Character> sx = new HashSet<>();
        for (char c : x.toCharArray()) {
            sx.add(c);
        }

        int common = 0;
        for (char c : y.toCharArray()) {
            if (sx.contains(c)) {
                common++;
            }
        }

        return common / (double) Math.max(x.length(), y.length());
    }

    private Set<String> tokens(String text) {
        Set<String> out = new HashSet<>();
        if (text == null || text.isEmpty()) {
            return out;
        }

        String[] parts = text.split("\\s+");
        for (String p : parts) {
            if (!p.isEmpty()) {
                out.add(p);
            }
        }

        String compact = text.replace(" ", "");
        int max = Math.min(compact.length(), 24);

        for (int i = 0; i < max; i++) {
            out.add(String.valueOf(compact.charAt(i)));
        }
        for (int i = 0; i + 1 < max; i++) {
            out.add(compact.substring(i, i + 2));
        }

        return out;
    }

    private String normalize(String s) {
        return s.toLowerCase()
                .replaceAll("[^\\p{IsHan}a-z0-9]+", " ")
                .trim();
    }

    private static class QaItem {
        int id;
        String category;
        String question;
        String answer;
        List<String> searchTexts = new ArrayList<>();
    }

    private static class SearchHit {
        QaItem item;
        double score;
        String bestMatch;

        SearchHit(QaItem item, double score, String bestMatch) {
            this.item = item;
            this.score = score;
            this.bestMatch = bestMatch;
        }

        double getScore() {
            return score;
        }
    }
}
