package com.contest;

import org.apache.poi.openxml4j.util.ZipSecureFile;
import org.apache.poi.poifs.filesystem.FileMagic;
import org.apache.poi.sl.usermodel.GroupShape;
import org.apache.poi.sl.usermodel.PictureShape;
import org.apache.poi.sl.usermodel.Shape;
import org.apache.poi.sl.usermodel.Slide;
import org.apache.poi.sl.usermodel.SlideShow;
import org.apache.poi.sl.usermodel.TableCell;
import org.apache.poi.sl.usermodel.TableShape;
import org.apache.poi.sl.usermodel.TextShape;
import org.apache.poi.sl.usermodel.SlideShowFactory;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * PPT解析工具
 */
public class PptParserUtil {

    private static final List<String> KEYWORDS = Arrays.asList(
            "技能树", "职业规划", "CI/CD", "个人品牌", "认证培训",
            "编程语言", "算法", "数据结构", "软件开发", "自动化测试"
    );
    // 适度放宽 POI 对压缩比的安全阈值，避免正常课件（含高压缩图片）被误判 Zip bomb
    private static final double ZIP_MIN_INFLATE_RATIO = 0.001;
    private static final long ZIP_MAX_ENTRY_SIZE = 200L * 1024 * 1024;
    private static final long ZIP_MAX_TEXT_SIZE = 50L * 1024 * 1024;
    private static final long ZIP_MAX_FILE_COUNT = 20000;
    private static final String PARSE_FAILURE_PREFIX = "解析失败：";

    /**
     * 解析PPT生成HTML（InputStream版）
     */
    public static String extractTextWithHtml(InputStream is) {
        configureZipSecurity();

        try (SlideShow<?, ?> ppt = openSlideShow(is)) {
            return generatePptHtml(ppt, null, null);
        } catch (Exception e) {
            e.printStackTrace();
            return "<div style='color:#ff4d4f;background:#fff2f0;border:1px solid #ffccc7;border-radius:12px;padding:20px;margin:20px;max-width:1200px;'>"
                    + "<h3 style='margin-bottom:10px;font-size:18px;'>❌ PPT解析失败</h3>"
                    + "<p style='line-height:1.6;font-size:16px;'>错误原因：" + e.getClass().getSimpleName() + " - " + e.getMessage() + "</p>"
                    + "<p>请尝试：<br>1. 更换未加密的PPT文件<br>2. 检查文件是否损坏<br>3. 确认文件为.ppt/.pptx格式</p>"
                    + "</div>";
        }
    }

    /**
     * 解析PPT生成HTML（文件路径版）
     */
    public static String extractTextWithHtml(String path) {
        configureZipSecurity();
        try (FileInputStream fis = new FileInputStream(path);
             SlideShow<?, ?> ppt = openSlideShow(fis)) {
            return generatePptHtml(ppt, null, null);
        } catch (Exception e) {
            return "<div style='color:#ff4d4f;background:#fff2f0;border:1px solid #ffccc7;border-radius:12px;padding:20px;margin:20px;max-width:1200px;'>"
                    + "<h3 style='margin-bottom:10px;font-size:18px;'>❌ PPT解析失败</h3>"
                    + "<p style='line-height:1.6;font-size:16px;'>错误原因：" + e.getMessage() + "</p>"
                    + "</div>";
        }
    }

    private static final Pattern SLIDE_ENTRY = Pattern.compile("^ppt/slides/slide(\\d+)\\.xml$");
    private static final Pattern XML_TEXT = Pattern.compile("<a:t[^>]*>(.*?)</a:t>", Pattern.DOTALL);

    /**
     * 提取PPT纯文本（InputStream版）。
     * .pptx 走 ZIP+XML 轻量抽取；.ppt 走 POI。
     */
    public static String extractRawText(InputStream is) {
        return extractRawText(is, "");
    }

    /**
     * @param fileNameHint 原始文件名，用于判断 .ppt / .pptx
     */
    public static String extractRawText(InputStream is, String fileNameHint) {
        configureZipSecurity();
        String lower = fileNameHint == null ? "" : fileNameHint.toLowerCase();
        boolean legacyPpt = lower.endsWith(".ppt") && !lower.endsWith(".pptx");
        if (!legacyPpt) {
            // 默认按 pptx 轻量路径（避免同一流被消费后无法回退）
            try {
                String zipText = extractRawTextFromPptxZip(is);
                if (zipText != null && !zipText.trim().isEmpty()) {
                    System.out.println("✅ ZIP轻量提取PPT文本长度：" + zipText.length());
                    return zipText;
                }
                return PARSE_FAILURE_PREFIX + "课件中未识别到可提取的文本";
            } catch (Exception zipErr) {
                System.err.println("❌ ZIP轻量提取失败：" + zipErr.getMessage());
                return PARSE_FAILURE_PREFIX + normalizeErrorMessage(zipErr);
            }
        }
        try (SlideShow<?, ?> ppt = openSlideShow(is)) {
            String rawText = generatePptRawText(ppt, null);
            System.out.println("✅ 提取的PPT纯文本：" + rawText);
            return rawText;
        } catch (Exception e) {
            System.err.println("❌ 提取纯文本失败：" + e.getMessage());
            return PARSE_FAILURE_PREFIX + normalizeErrorMessage(e);
        }
    }

    /** 兼容旧调用：带预览目录时仍用 POI（当前秒解析路径不再使用）。 */
    public static String extractRawText(InputStream is, Path slideImageDir) {
        if (slideImageDir == null) {
            return extractRawText(is, ".pptx");
        }
        configureZipSecurity();
        try (SlideShow<?, ?> ppt = openSlideShow(is)) {
            return generatePptRawText(ppt, slideImageDir);
        } catch (Exception e) {
            return PARSE_FAILURE_PREFIX + normalizeErrorMessage(e);
        }
    }

    /**
     * 只读 ppt/slides/slideN.xml 中的 a:t 文本节点，不解析图片/主题/媒体。
     */
    public static String extractRawTextFromPptxZip(InputStream is) throws Exception {
        InputStream in = is instanceof BufferedInputStream ? is : new BufferedInputStream(is);
        List<SlideXml> slides = new ArrayList<>();
        try (ZipInputStream zis = new ZipInputStream(in)) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                String name = entry.getName() == null ? "" : entry.getName().replace('\\', '/');
                Matcher m = SLIDE_ENTRY.matcher(name);
                if (!m.matches()) {
                    continue;
                }
                int page = Integer.parseInt(m.group(1));
                String xml = readUtf8(zis);
                slides.add(new SlideXml(page, extractTextsFromSlideXml(xml)));
            }
        }
        if (slides.isEmpty()) {
            throw new IllegalStateException("未找到 ppt/slides/slide*.xml");
        }
        slides.sort(Comparator.comparingInt(s -> s.page));
        List<String> lines = new ArrayList<>();
        for (SlideXml slide : slides) {
            lines.add("=== 第" + slide.page + "页 ===");
            if (slide.texts.isEmpty()) {
                lines.add("（此页无文本内容）");
            } else {
                lines.addAll(slide.texts);
            }
        }
        return String.join("\n", lines);
    }

    private static List<String> extractTextsFromSlideXml(String xml) {
        List<String> texts = new ArrayList<>();
        if (xml == null || xml.isEmpty()) {
            return texts;
        }
        Matcher matcher = XML_TEXT.matcher(xml);
        while (matcher.find()) {
            String raw = matcher.group(1);
            if (raw == null) {
                continue;
            }
            String text = raw
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&quot;", "\"")
                    .replace("&apos;", "'")
                    .replace("&#39;", "'")
                    .replaceAll("</?[^>]+>", "")
                    .replace('\u000B', '\n')
                    .trim();
            if (!text.isEmpty()) {
                texts.add(text);
            }
        }
        return texts;
    }

    private static String readUtf8(InputStream in) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) >= 0) {
            bos.write(buf, 0, n);
        }
        return bos.toString(StandardCharsets.UTF_8.name());
    }

    private static final class SlideXml {
        final int page;
        final List<String> texts;

        SlideXml(int page, List<String> texts) {
            this.page = page;
            this.texts = texts;
        }
    }

    /**
     * 解析PPT生成HTML，并将每页渲染成图片预览。
     */
    public static String extractTextWithHtml(InputStream is, Path slideImageDir, String slideImageUrlPrefix) {
        configureZipSecurity();

        try (SlideShow<?, ?> ppt = openSlideShow(is)) {
            List<String> imageUrls = renderSlideImages(ppt, slideImageDir, slideImageUrlPrefix);
            return generatePptHtml(ppt, imageUrls, slideImageUrlPrefix);
        } catch (Exception e) {
            e.printStackTrace();
            return "<div style='color:#ff4d4f;background:#fff2f0;border:1px solid #ffccc7;border-radius:12px;padding:20px;margin:20px;max-width:1200px;'>"
                    + "<h3 style='margin-bottom:10px;font-size:18px;'>❌ PPT解析失败</h3>"
                    + "<p style='line-height:1.6;font-size:16px;'>错误原因：" + e.getClass().getSimpleName() + " - " + e.getMessage() + "</p>"
                    + "<p>请尝试：<br>1. 更换未加密的PPT文件<br>2. 检查文件是否损坏<br>3. 确认文件为.ppt/.pptx格式</p>"
                    + "</div>";
        }
    }

    /**
     * 提取PPT纯文本（文件路径版）
     */
    public static String extractRawText(String path) {
        configureZipSecurity();
        try (FileInputStream fis = new FileInputStream(path);
             SlideShow<?, ?> ppt = openSlideShow(fis)) {
            return generatePptRawText(ppt, null);
        } catch (Exception e) {
            return PARSE_FAILURE_PREFIX + normalizeErrorMessage(e);
        }
    }

    /**
     * 生成PPT HTML（无分页，显示全部）
     */
    private static String generatePptHtml(SlideShow<?, ?> ppt, List<String> slideImageUrls, String slideImageUrlPrefix) {
        List<? extends Slide<?, ?>> slides = ppt.getSlides();
        int totalPages = slides.size();
        boolean hasRenderedPreview = slideImageUrls != null && !slideImageUrls.isEmpty();

        String navHtml = generateNavigation(slides);
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html>")
                .append("<html lang='zh-CN'>")
                .append("<head>")
                .append("<meta charset='UTF-8'>")
                .append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
                .append("<title>PPT解析结果</title>")
                .append("<style>")
                .append("* {margin:0;padding:0;box-sizing:border-box;}")
                .append("body {font-family: 'Microsoft YaHei', sans-serif;background:#f5f7fa;}")
                .append(".ppt-container{max-width:1200px;margin:0 auto;padding:20px;}")
                .append(".page-summary{background:#e6f7ff;border-radius:12px;padding:16px 20px;margin-bottom:24px;font-size:16px;color:#1890ff;box-shadow:0 2px 8px rgba(0,0,0,0.05);}")
                .append(".page-summary strong{color:#096dd9;font-size:18px;}")
                .append(".nav-container{background:#fff;border-radius:12px;padding:20px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.05);}")
                .append(".nav-title{font-size:18px;font-weight:600;color:#333;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #e8e8e8;}")
                .append(".nav-list{display:flex;flex-wrap:wrap;gap:8px;}")
                .append(".nav-item{padding:6px 12px;background:#f0f7ff;border-radius:6px;color:#1890ff;text-decoration:none;transition:all 0.2s ease;cursor:pointer;}")
                .append(".nav-item:hover{background:#1890ff;color:#fff;}")
                .append(".slides-wrapper{display:flex;flex-direction:column;gap:16px;}")
                .append(".slide-card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:24px;margin:0;box-shadow:0 2px 8px rgba(0,0,0,0.05);transition:all 0.3s ease;}")
                .append(".slide-card:hover{box-shadow:0 6px 16px rgba(0,0,0,0.1);transform:translateY(-2px);}")
                .append(".slide-title{color:#096dd9;font-size:20px;font-weight:600;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #e6f7ff;}")
                .append(".slide-visual{margin-bottom:16px;border:1px solid #d9e8ff;background:#f8fbff;border-radius:10px;padding:10px;}")
                .append(".slide-visual-title{font-size:13px;font-weight:700;color:#385f9f;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:8px;}")
                .append(".slide-visual img{display:block;width:100%;height:auto;border-radius:8px;background:#fff;box-shadow:0 3px 10px rgba(25,70,140,.08);}")
                .append(".slide-visual-fallback{color:#7a8699;font-size:13px;line-height:1.7;}")
                .append(".slide-content{color:#333;line-height:1.8;font-size:16px;}")
                .append(".content-item{margin:10px 0;padding:10px 14px;border-left:4px solid #1890ff;background:#f6ffed;border-radius:6px;}")
                .append(".media-item{margin:10px 0;padding:10px 14px;border-left:4px solid #7c3aed;background:#f5f3ff;border-radius:6px;color:#5b21b6;}")
                .append(".keyword{color:#ff4d4f;font-weight:600;background:#fff2f0;padding:2px 4px;border-radius:3px;}")
                .append(".empty-tip{color:#999;font-style:italic;padding:16px;background:#f5f5f5;border-radius:8px;text-align:center;}")
                .append(".back-to-top{position:fixed;bottom:30px;right:30px;width:48px;height:48px;background:#1890ff;color:#fff;border-radius:50%;display:flex;justify-content:center;align-items:center;font-size:20px;box-shadow:0 4px 12px rgba(24,144,255,0.3);cursor:pointer;opacity:0;visibility:hidden;transition:all 0.3s ease;z-index:999;}")
                .append(".back-to-top.show{opacity:1;visibility:visible;}")
                .append("</style>")
                .append("</head>")
                .append("<body>");

        html.append("<div class='ppt-container'>");
        html.append("<div class='page-summary'>✅ PPT解析完成，共 <strong>").append(totalPages).append("</strong> 页</div>");
        html.append(navHtml);
        html.append("<div class='slides-wrapper'>");

        // 显示所有页面
        for (int i = 0; i < slides.size(); i++) {
            String imageUrl = hasRenderedPreview && i < slideImageUrls.size() ? slideImageUrls.get(i) : "";
            html.append("<div id='page-").append(i+1).append("'>")
                    .append(generateSlideCard(slides.get(i), i+1, imageUrl))
                    .append("</div>");
        }

        html.append("</div>");
        html.append("<div class='back-to-top' id='backToTop'>↑</div>");
        html.append("</div>");

        // 回到顶部 + 目录跳转
        html.append("<script>")
                .append("document.addEventListener('DOMContentLoaded', function() {")
                .append("const backToTop = document.getElementById('backToTop');")
                .append("window.onscroll = () => {")
                .append("  backToTop.classList.toggle('show', window.scrollY > 300);")
                .append("}")
                .append("backToTop.onclick = () => {")
                .append("  window.scrollTo({top: 0, behavior: 'smooth'});")
                .append("}")
                .append("document.querySelectorAll('.nav-item').forEach(item => {")
                .append("  item.onclick = (e) => {")
                .append("    e.preventDefault();")
                .append("    const pageNum = parseInt(item.dataset.page);")
                .append("    if (!pageNum) return;")
                .append("    const target = document.getElementById('page-' + pageNum);")
                .append("    if (target) target.scrollIntoView({behavior: 'smooth', block: 'start'});")
                .append("  }")
                .append("});")
                .append("});")
                .append("</script>")
                .append("</body>")
                .append("</html>");

        return html.toString();
    }

    /**
     * 生成PPT纯文本
     */
    private static String generatePptRawText(SlideShow<?, ?> ppt, Path slideImageDir) {
        List<String> textList = new ArrayList<>();
        List<? extends Slide<?, ?>> slides = ppt.getSlides();
        // 秒解析：只抽文字；页图渲染 / 视觉识别已关闭
        int maxPages = slides.size();
        boolean allowVision = false;
        int remainingVisionPages = 0;

        for (int i = 0; i < maxPages; i++) {
            Slide<?, ?> slide = slides.get(i);
            textList.add("=== 第" + (i+1) + "页 ===");
            boolean hasText = false;
            List<String> pageTexts = new ArrayList<>();
            for (Shape<?, ?> shape : slide.getShapes()) {
                List<String> shapeTexts = extractShapeTexts(shape);
                if (!shapeTexts.isEmpty()) {
                    hasText = true;
                    pageTexts.addAll(shapeTexts);
                    textList.addAll(shapeTexts);
                }
            }
            int pictureCount = countPictures(slide.getShapes());
            if (pictureCount > 0) {
                List<String> pictureNames = extractPictureNames(slide.getShapes());
                StringBuilder imgMeta = new StringBuilder("【图片/图形】本页含 ")
                        .append(pictureCount).append(" 个图片对象");
                if (!pictureNames.isEmpty()) {
                    imgMeta.append("：").append(String.join("、", pictureNames));
                }
                textList.add(imgMeta.toString());
                hasText = true;
            }

            // 仅当显式传入预览目录时才做视觉识别（默认解析路径不再传）
            if (allowVision && remainingVisionPages > 0 && pictureCount > 0) {
                Path imagePath = slideImageDir.resolve("slide-" + (i + 1) + ".png");
                if (Files.isRegularFile(imagePath)) {
                    String imageSummary = AiApiUtil.describeSlideImage(
                            imagePath,
                            String.join("\n", pageTexts),
                            i + 1
                    );
                    if (imageSummary != null && !imageSummary.trim().isEmpty()) {
                        textList.add("【图片内容识别】" + imageSummary.trim());
                        hasText = true;
                    }
                    remainingVisionPages--;
                }
            }
            if (!hasText) {
                textList.add("（此页无文本内容）");
            }
        }

        String rawText = String.join("\n", textList);
        System.out.println("✅ 最终生成的PPT纯文本长度：" + rawText.length());
        return rawText;
    }

    /**
     * 生成单页PPT卡片
     */
    private static String generateSlideCard(Slide<?, ?> slide, int pageNum, String slideImageUrl) {
        StringBuilder card = new StringBuilder();
        card.append("<div class='slide-card'>")
                .append("<div class='slide-title'>📄 第").append(pageNum).append("页</div>")
                .append("<div class='slide-content'>");

        boolean hasContent = false;
        if (slideImageUrl != null && !slideImageUrl.trim().isEmpty()) {
            hasContent = true;
            card.append("<div class='slide-visual'>")
                    .append("<div class='slide-visual-title'><span>页面视觉预览</span><span>图片/图形已保留</span></div>")
                    .append("<img src='").append(escapeHtmlAttribute(slideImageUrl)).append("' alt='第").append(pageNum).append("页PPT视觉预览'>")
                    .append("</div>");
        }

        for (Shape<?, ?> shape : slide.getShapes()) {
            for (String text : extractShapeTexts(shape)) {
                hasContent = true;
                card.append("<div class='content-item'>").append(highlightKeywords(escapeHtml(text))).append("</div>");
            }
        }

        int pictureCount = countPictures(slide.getShapes());
        if (pictureCount > 0) {
            hasContent = true;
            card.append("<div class='media-item'>本页检测到 ")
                    .append(pictureCount)
                    .append(" 个图片或图形对象，已在上方页面预览中保留。</div>");
        }

        if (!hasContent) {
            card.append("<div class='empty-tip'>此页面无文本内容</div>");
        }

        card.append("</div></div>");
        return card.toString();
    }

    /**
     * 关键词高亮
     */
    private static String highlightKeywords(String text) {
        String result = text;
        for (String keyword : KEYWORDS) {
            if (result.contains(keyword)) {
                result = result.replaceAll(Pattern.quote(keyword), "<span class='keyword'>" + keyword + "</span>");
            }
        }
        return result;
    }

    /**
     * 生成目录导航
     */
    private static String generateNavigation(List<? extends Slide<?, ?>> slides) {
        StringBuilder nav = new StringBuilder();
        nav.append("<div class='nav-container'>")
                .append("<div class='nav-title'>📚 目录导航</div>")
                .append("<div class='nav-list'>");

        int navPageCount = Math.min(slides.size(), 10);
        for (int i = 1; i <= navPageCount; i++) {
            nav.append("<a href='javascript:void(0);' class='nav-item' data-page='").append(i).append("'>第").append(i).append("页</a>");
        }

        if (slides.size() > 10) {
            nav.append("<span style='color:#999;'>...</span>");
        }

        nav.append("</div></div>");
        return nav.toString();
    }

    private static SlideShow<?, ?> openSlideShow(InputStream is) throws Exception {
        InputStream checked = FileMagic.prepareToCheckMagic(is);
        return SlideShowFactory.create(checked, null);
    }

    public static boolean isParseFailure(String text) {
        if (text == null) {
            return false;
        }
        return text.contains(PARSE_FAILURE_PREFIX) || text.contains("PPT解析失败");
    }

    public static String cleanParseFailureMessage(String rawText) {
        if (rawText == null || rawText.trim().isEmpty()) {
            return "PPT解析失败：请确认文件未加密、未损坏，且格式为 .ppt/.pptx";
        }
        String message = rawText.trim();
        if (message.startsWith(PARSE_FAILURE_PREFIX)) {
            message = message.substring(PARSE_FAILURE_PREFIX.length()).trim();
        }
        message = message.replaceAll("<[^>]+>", " ")
                .replace("❌", "")
                .replaceAll("\\s+", " ")
                .trim();
        return "PPT解析失败：" + message;
    }

    private static List<String> extractShapeTexts(Shape<?, ?> shape) {
        List<String> texts = new ArrayList<>();
        if (shape instanceof GroupShape) {
            GroupShape<?, ?> groupShape = (GroupShape<?, ?>) shape;
            for (Shape<?, ?> child : groupShape.getShapes()) {
                texts.addAll(extractShapeTexts(child));
            }
            return texts;
        }

        if (shape instanceof TableShape) {
            TableShape<?, ?> tableShape = (TableShape<?, ?>) shape;
            for (int row = 0; row < tableShape.getNumberOfRows(); row++) {
                List<String> rowTexts = new ArrayList<>();
                for (int col = 0; col < tableShape.getNumberOfColumns(); col++) {
                    TableCell<?, ?> cell = tableShape.getCell(row, col);
                    if (cell == null || cell.isMerged()) {
                        continue;
                    }
                    String text = normalizeText(cell.getText());
                    if (!text.isEmpty()) {
                        rowTexts.add(text);
                    }
                }
                if (!rowTexts.isEmpty()) {
                    texts.add(String.join(" | ", rowTexts));
                }
            }
            return texts;
        }

        if (shape instanceof TextShape) {
            String text = normalizeText(((TextShape<?, ?>) shape).getText());
            if (!text.isEmpty()) {
                texts.add(text);
            }
        }
        return texts;
    }

    private static int countPictures(List<? extends Shape<?, ?>> shapes) {
        int count = 0;
        for (Shape<?, ?> shape : shapes) {
            if (shape instanceof GroupShape) {
                count += countPictures(((GroupShape<?, ?>) shape).getShapes());
            } else if (shape instanceof PictureShape) {
                count++;
            }
        }
        return count;
    }

    private static List<String> extractPictureNames(List<? extends Shape<?, ?>> shapes) {
        List<String> names = new ArrayList<>();
        collectPictureNames(shapes, names);
        if (names.size() > 6) {
            return new ArrayList<>(names.subList(0, 6));
        }
        return names;
    }

    private static void collectPictureNames(List<? extends Shape<?, ?>> shapes, List<String> names) {
        if (shapes == null || names.size() >= 6) {
            return;
        }
        for (Shape<?, ?> shape : shapes) {
            if (names.size() >= 6) {
                return;
            }
            if (shape instanceof GroupShape) {
                collectPictureNames(((GroupShape<?, ?>) shape).getShapes(), names);
            } else if (shape instanceof PictureShape) {
                String name = shape.getShapeName();
                if (name == null || name.trim().isEmpty()) {
                    name = "图片" + (names.size() + 1);
                }
                names.add(name.trim());
            }
        }
    }

    private static List<String> renderSlideImages(
            SlideShow<?, ?> ppt,
            Path slideImageDir,
            String slideImageUrlPrefix
    ) {
        List<String> urls = new ArrayList<>();
        if (slideImageDir == null || slideImageUrlPrefix == null || slideImageUrlPrefix.trim().isEmpty()) {
            return urls;
        }
        try {
            Files.createDirectories(slideImageDir);
            Dimension pageSize = ppt.getPageSize();
            List<? extends Slide<?, ?>> slides = ppt.getSlides();
            for (int i = 0; i < slides.size(); i++) {
                String fileName = "slide-" + (i + 1) + ".png";
                Path imagePath = slideImageDir.resolve(fileName);
                try {
                    renderSlideImage(slides.get(i), pageSize, imagePath);
                    urls.add(trimTrailingSlash(slideImageUrlPrefix) + "/" + fileName);
                } catch (Exception slideError) {
                    System.err.println("⚠️ 第 " + (i + 1) + " 页PPT图片预览生成失败：" + slideError.getMessage());
                    urls.add("");
                }
            }
        } catch (Exception e) {
            System.err.println("⚠️ PPT页面图片预览生成失败：" + e.getMessage());
            urls.clear();
        }
        return urls;
    }

    private static void renderSlideImage(Slide<?, ?> slide, Dimension pageSize, Path imagePath) throws Exception {
        int width = Math.max(1, pageSize.width);
        int height = Math.max(1, pageSize.height);
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics();
        try {
            graphics.setPaint(Color.WHITE);
            graphics.fillRect(0, 0, width, height);
            graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            graphics.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            graphics.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
            slide.draw(graphics);
        } finally {
            graphics.dispose();
        }
        ImageIO.write(image, "png", imagePath.toFile());
    }

    private static String trimTrailingSlash(String value) {
        String result = value == null ? "" : value.trim();
        while (result.endsWith("/")) {
            result = result.substring(0, result.length() - 1);
        }
        return result;
    }

    private static String normalizeText(String text) {
        if (text == null) {
            return "";
        }
        return text.replace('\u000B', '\n').trim();
    }

    private static String normalizeErrorMessage(Exception e) {
        if (e == null) {
            return "未知错误";
        }
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            return e.getClass().getSimpleName();
        }
        return message.trim();
    }

    private static String escapeHtml(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        return text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;")
                .replace("\n", "<br>");
    }

    private static String escapeHtmlAttribute(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        return text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }

    private static void configureZipSecurity() {
        ZipSecureFile.setMinInflateRatio(ZIP_MIN_INFLATE_RATIO);
        ZipSecureFile.setMaxEntrySize(ZIP_MAX_ENTRY_SIZE);
        ZipSecureFile.setMaxTextSize(ZIP_MAX_TEXT_SIZE);
        ZipSecureFile.setMaxFileCount(ZIP_MAX_FILE_COUNT);
    }
}
