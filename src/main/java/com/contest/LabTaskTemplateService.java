package com.contest;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class LabTaskTemplateService {

    public ProjectService.LabTask generate(ProjectService.ProjectRecord project) {
        String language = normalizeLanguage(project == null ? "" : project.getProgrammingLanguage());
        ProjectService.LabTask task = new ProjectService.LabTask();
        task.setId("task_" + UUID.randomUUID().toString().replace("-", ""));
        task.setLanguage(language);
        task.setPublished(true);
        task.setTimeLimitMs(2000);
        task.setCreatedAt(Instant.now().toString());
        task.setTestCases(new ArrayList<>());

        if ("SQL".equals(language)) {
            task.setTitle("课程成绩查询");
            task.setDescription("编写 SQL：从 course_score 表查询 score 不低于 60 的 student_name 与 score，并按 score 降序排列。");
            task.setJudgeMode("sql_rules");
            task.setStarterCode("SELECT student_name, score\nFROM course_score\n-- TODO：补充筛选条件与排序规则\n;");
            task.setSampleInput("表：course_score(student_name, score)");
            task.setSampleOutput("必须包含 SELECT、FROM、WHERE、ORDER BY 与 DESC");
            addCase(task, "select\nstudent_name\nscore\nfrom\ncourse_score", "基础查询结构");
            addCase(task, "where\nscore\n>=\n60", "及格条件");
            addCase(task, "order by\nscore\ndesc", "降序排序");
            return task;
        }

        task.setTitle("两数求和与输入输出");
        task.setDescription("读取两个整数，输出它们的和。要求只输出结果，不添加额外提示文本。");
        task.setJudgeMode("io");
        task.setSampleInput("3 5");
        task.setSampleOutput("8");
        addCase(task, "3 5\n", "8");
        addCase(task, "-2 7\n", "5");
        addCase(task, "100 250\n", "350");

        if ("Python".equals(language)) {
            task.setStarterCode("a, b = map(int, input().split())\n# TODO：计算并输出结果\nprint(0)\n");
        } else if ("JavaScript".equals(language)) {
            task.setStarterCode("const fs = require('fs');\nconst [a, b] = fs.readFileSync(0, 'utf8').trim().split(/\\s+/).map(Number);\n// TODO：计算并输出结果\nconsole.log(0);\n");
        } else {
            task.setLanguage("Java");
            task.setStarterCode("import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        int a = scanner.nextInt();\n        int b = scanner.nextInt();\n        // TODO：计算并输出结果\n        System.out.println(0);\n    }\n}\n");
        }
        return task;
    }

    private void addCase(ProjectService.LabTask task, String input, String expected) {
        ProjectService.LabTestCase testCase = new ProjectService.LabTestCase();
        testCase.setId("case_" + UUID.randomUUID().toString().replace("-", ""));
        testCase.setInputText(input);
        testCase.setExpectedOutput(expected);
        testCase.setSortOrder(task.getTestCases().size());
        task.getTestCases().add(testCase);
    }

    private String normalizeLanguage(String value) {
        String language = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        if (language.contains("python")) return "Python";
        if (language.contains("javascript") || language.equals("js")) return "JavaScript";
        if (language.contains("sql")) return "SQL";
        return "Java";
    }
}
