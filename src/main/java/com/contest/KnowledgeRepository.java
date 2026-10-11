package com.contest;

import org.springframework.stereotype.Repository;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Repository
public class KnowledgeRepository {

    private final DatabaseStore databaseStore;

    public KnowledgeRepository(DatabaseStore databaseStore) {
        this.databaseStore = databaseStore;
    }

    public void upsertDocument(Document document, List<ChunkRow> chunks) throws SQLException {
        databaseStore.initSchema();
        try (Connection conn = databaseStore.connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement documentPs = conn.prepareStatement(
                    "INSERT INTO knowledge_documents("
                            + "id,course_code,title,source_url,source_type,publisher,version_label,"
                            + "license_name,license_url,quality_tier,quality_score,source_updated_at,"
                            + "fetched_at,checksum_sha256,local_path,content_format,active,created_at,updated_at"
                            + ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                            + "ON DUPLICATE KEY UPDATE course_code=VALUES(course_code),title=VALUES(title),"
                            + "source_type=VALUES(source_type),publisher=VALUES(publisher),"
                            + "version_label=VALUES(version_label),license_name=VALUES(license_name),"
                            + "license_url=VALUES(license_url),quality_tier=VALUES(quality_tier),"
                            + "quality_score=VALUES(quality_score),source_updated_at=VALUES(source_updated_at),"
                            + "fetched_at=VALUES(fetched_at),checksum_sha256=VALUES(checksum_sha256),"
                            + "local_path=VALUES(local_path),content_format=VALUES(content_format),"
                            + "active=1,updated_at=VALUES(updated_at)");
                 PreparedStatement deactivatePs = conn.prepareStatement(
                         "UPDATE knowledge_chunks SET active=0 WHERE document_id=?");
                 PreparedStatement chunkPs = conn.prepareStatement(
                         "INSERT INTO knowledge_chunks("
                                 + "id,document_id,course_code,chunk_type,section_title,chunk_index,"
                                 + "content,search_text,token_count,quality_score,active,created_at"
                                 + ") VALUES(?,?,?,?,?,?,?,?,?,?,1,?) "
                                 + "ON DUPLICATE KEY UPDATE chunk_type=VALUES(chunk_type),"
                                 + "section_title=VALUES(section_title),chunk_index=VALUES(chunk_index),"
                                 + "content=VALUES(content),search_text=VALUES(search_text),"
                                 + "token_count=VALUES(token_count),quality_score=VALUES(quality_score),active=1")) {
                bindDocument(documentPs, document);
                documentPs.executeUpdate();

                deactivatePs.setString(1, document.id());
                deactivatePs.executeUpdate();

                for (ChunkRow chunk : chunks) {
                    chunkPs.setString(1, chunk.id());
                    chunkPs.setString(2, document.id());
                    chunkPs.setString(3, document.courseCode());
                    chunkPs.setString(4, chunk.chunkType());
                    chunkPs.setString(5, chunk.sectionTitle());
                    chunkPs.setInt(6, chunk.chunkIndex());
                    chunkPs.setString(7, chunk.content());
                    chunkPs.setString(8, chunk.searchText());
                    chunkPs.setInt(9, chunk.tokenCount());
                    chunkPs.setInt(10, document.qualityScore());
                    chunkPs.setString(11, Instant.now().toString());
                    chunkPs.addBatch();
                }
                chunkPs.executeBatch();
                conn.commit();
            } catch (SQLException e) {
                conn.rollback();
                throw e;
            }
        }
    }

    public void upsertEvaluationCase(EvaluationCase item) throws SQLException {
        databaseStore.initSchema();
        try (Connection conn = databaseStore.connection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO knowledge_eval_cases("
                             + "id,course_code,question_type,question,expected_keywords,"
                             + "expected_source_url,top_k,enabled,created_at,updated_at"
                             + ") VALUES(?,?,?,?,?,?,?,1,?,?) "
                             + "ON DUPLICATE KEY UPDATE course_code=VALUES(course_code),"
                             + "question_type=VALUES(question_type),question=VALUES(question),"
                             + "expected_keywords=VALUES(expected_keywords),"
                             + "expected_source_url=VALUES(expected_source_url),top_k=VALUES(top_k),"
                             + "enabled=1,updated_at=VALUES(updated_at)")) {
            String now = Instant.now().toString();
            ps.setString(1, item.id());
            ps.setString(2, item.courseCode());
            ps.setString(3, item.questionType());
            ps.setString(4, item.question());
            ps.setString(5, item.expectedKeywords());
            ps.setString(6, item.expectedSourceUrl());
            ps.setInt(7, item.topK());
            ps.setString(8, now);
            ps.setString(9, now);
            ps.executeUpdate();
        }
    }

    public List<Candidate> loadCandidates(String courseCode, int limit) throws SQLException {
        databaseStore.initSchema();
        List<Candidate> rows = new ArrayList<>();
        String sql = "SELECT c.id,c.document_id,c.course_code,c.chunk_type,c.section_title,"
                + "c.content,c.search_text,c.quality_score,d.title,d.source_url,d.publisher,"
                + "d.version_label,d.license_name,d.license_url,d.quality_tier,d.source_updated_at "
                + "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
                + "WHERE c.course_code=? AND c.active=1 AND d.active=1 "
                + "ORDER BY c.quality_score DESC,c.document_id,c.chunk_index LIMIT ?";
        try (Connection conn = databaseStore.connection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, courseCode);
            ps.setInt(2, Math.max(1, Math.min(limit, 10000)));
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    rows.add(new Candidate(
                            rs.getString("id"),
                            rs.getString("document_id"),
                            rs.getString("course_code"),
                            rs.getString("chunk_type"),
                            rs.getString("section_title"),
                            rs.getString("content"),
                            rs.getString("search_text"),
                            rs.getInt("quality_score"),
                            rs.getString("title"),
                            rs.getString("source_url"),
                            rs.getString("publisher"),
                            rs.getString("version_label"),
                            rs.getString("license_name"),
                            rs.getString("license_url"),
                            rs.getString("quality_tier"),
                            rs.getString("source_updated_at")
                    ));
                }
            }
        }
        return rows;
    }

    public List<EvaluationCase> loadEvaluationCases() throws SQLException {
        databaseStore.initSchema();
        List<EvaluationCase> rows = new ArrayList<>();
        try (Connection conn = databaseStore.connection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT id,course_code,question_type,question,expected_keywords,"
                             + "expected_source_url,top_k FROM knowledge_eval_cases "
                             + "WHERE enabled=1 ORDER BY course_code,id");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                rows.add(new EvaluationCase(
                        rs.getString("id"),
                        rs.getString("course_code"),
                        rs.getString("question_type"),
                        rs.getString("question"),
                        rs.getString("expected_keywords"),
                        rs.getString("expected_source_url"),
                        rs.getInt("top_k")
                ));
            }
        }
        return rows;
    }

    public void insertEvaluationRun(
            String id,
            String caseId,
            boolean passed,
            String matchedKeywords,
            String topDocumentId,
            double topScore,
            String details
    ) throws SQLException {
        databaseStore.initSchema();
        try (Connection conn = databaseStore.connection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO knowledge_eval_runs("
                             + "id,case_id,passed,matched_keywords,top_document_id,top_score,details,created_at"
                             + ") VALUES(?,?,?,?,?,?,?,?)")) {
            ps.setString(1, id);
            ps.setString(2, caseId);
            ps.setBoolean(3, passed);
            ps.setString(4, matchedKeywords);
            ps.setString(5, topDocumentId);
            ps.setDouble(6, topScore);
            ps.setString(7, details);
            ps.setString(8, Instant.now().toString());
            ps.executeUpdate();
        }
    }

    public Map<String, Object> stats() throws SQLException {
        databaseStore.initSchema();
        Map<String, Object> result = new LinkedHashMap<>();
        try (Connection conn = databaseStore.connection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT d.course_code,COUNT(DISTINCT d.id) document_count,"
                             + "COUNT(c.id) chunk_count,ROUND(AVG(d.quality_score),1) avg_quality "
                             + "FROM knowledge_documents d LEFT JOIN knowledge_chunks c "
                             + "ON c.document_id=d.id AND c.active=1 "
                             + "WHERE d.active=1 GROUP BY d.course_code ORDER BY d.course_code");
             ResultSet rs = ps.executeQuery()) {
            List<Map<String, Object>> courses = new ArrayList<>();
            int documents = 0;
            int chunks = 0;
            while (rs.next()) {
                Map<String, Object> row = new LinkedHashMap<>();
                int documentCount = rs.getInt("document_count");
                int chunkCount = rs.getInt("chunk_count");
                row.put("courseCode", rs.getString("course_code"));
                row.put("documentCount", documentCount);
                row.put("chunkCount", chunkCount);
                row.put("averageQuality", rs.getDouble("avg_quality"));
                courses.add(row);
                documents += documentCount;
                chunks += chunkCount;
            }
            result.put("documentCount", documents);
            result.put("chunkCount", chunks);
            result.put("courses", courses);
        }
        return result;
    }

    private void bindDocument(PreparedStatement ps, Document item) throws SQLException {
        ps.setString(1, item.id());
        ps.setString(2, item.courseCode());
        ps.setString(3, item.title());
        ps.setString(4, item.sourceUrl());
        ps.setString(5, item.sourceType());
        ps.setString(6, item.publisher());
        ps.setString(7, item.versionLabel());
        ps.setString(8, item.licenseName());
        ps.setString(9, item.licenseUrl());
        ps.setString(10, item.qualityTier());
        ps.setInt(11, item.qualityScore());
        ps.setString(12, item.sourceUpdatedAt());
        ps.setString(13, item.fetchedAt());
        ps.setString(14, item.checksumSha256());
        ps.setString(15, item.localPath());
        ps.setString(16, item.contentFormat());
        ps.setBoolean(17, true);
        ps.setString(18, item.createdAt());
        ps.setString(19, item.updatedAt());
    }

    public record Document(
            String id,
            String courseCode,
            String title,
            String sourceUrl,
            String sourceType,
            String publisher,
            String versionLabel,
            String licenseName,
            String licenseUrl,
            String qualityTier,
            int qualityScore,
            String sourceUpdatedAt,
            String fetchedAt,
            String checksumSha256,
            String localPath,
            String contentFormat,
            String createdAt,
            String updatedAt
    ) {
    }

    public record ChunkRow(
            String id,
            String chunkType,
            String sectionTitle,
            int chunkIndex,
            String content,
            String searchText,
            int tokenCount
    ) {
    }

    public record Candidate(
            String id,
            String documentId,
            String courseCode,
            String chunkType,
            String sectionTitle,
            String content,
            String searchText,
            int qualityScore,
            String documentTitle,
            String sourceUrl,
            String publisher,
            String versionLabel,
            String licenseName,
            String licenseUrl,
            String qualityTier,
            String sourceUpdatedAt
    ) {
    }

    public record EvaluationCase(
            String id,
            String courseCode,
            String questionType,
            String question,
            String expectedKeywords,
            String expectedSourceUrl,
            int topK
    ) {
    }
}
