package com.contest;

import com.baidu.aip.speech.AipSpeech;
import com.baidu.aip.speech.TtsResponse;
import com.baidu.aip.util.Util;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 语音合成：
 * 1) 若配置了百度密钥 → 百度 TTS（收费云）
 * 2) 否则优先免费 Edge TTS（tools/free_tts.py，无需 Key）
 * 3) 再不行用 Windows 自带朗读导出 WAV（完全离线免费）
 */
public class TtsUtil {
    private static final String APP_ID = env("BAIDU_TTS_APP_ID", "AI_TTS_APP_ID");
    private static final String API_KEY = env("BAIDU_TTS_API_KEY", "AI_TTS_API_KEY");
    private static final String SECRET_KEY = env("BAIDU_TTS_SECRET_KEY", "AI_TTS_SECRET_KEY");

    private static AipSpeech client;
    private static volatile String lastError = "";
    private static volatile String lastProvider = "";

    public static String getLastError() {
        return lastError == null ? "" : lastError;
    }

    public static String getLastProvider() {
        return lastProvider == null ? "" : lastProvider;
    }

    public static String textToSpeech(String text, String filePath) {
        return textToSpeech(text, filePath, null);
    }

    /**
     * @param voiceStyle 工作台音色：温柔女声 / 专业男声 / 活力主持（也可传 soft_female 等）
     */
    public static String textToSpeech(String text, String filePath, String voiceStyle) {
        lastError = "";
        lastProvider = "";
        if (text == null || text.trim().isEmpty()) {
            lastError = "无有效文本可合成";
            return "";
        }
        if (filePath == null || filePath.trim().isEmpty()) {
            lastError = "未指定输出文件路径";
            return "";
        }

        // 1) 百度（仅当环境变量齐全）
        if (hasBaiduKeys()) {
            String baidu = baiduTextToSpeech(text, filePath);
            if (baidu != null && !baidu.isEmpty()) {
                lastProvider = "baidu";
                return baidu;
            }
            // 百度失败时继续尝试免费通道，不直接放弃
            System.err.println("百度语音失败，尝试免费通道：" + lastError);
        }

        // 2) 免费 Edge TTS → mp3
        String edge = edgeTextToSpeech(text, filePath, voiceStyle);
        if (edge != null && !edge.isEmpty()) {
            lastProvider = "edge-tts-free";
            return edge;
        }

        // 3) Windows SAPI → wav（并把扩展名改为 .wav）
        String wavPath = toWavPath(filePath);
        String win = windowsSapiToWav(text, wavPath);
        if (win != null && !win.isEmpty()) {
            lastProvider = "windows-sapi-free";
            return win;
        }

        if (lastError == null || lastError.isEmpty()) {
            lastError = "免费与百度通道均不可用";
        }
        return "";
    }

    private static boolean hasBaiduKeys() {
        return !APP_ID.isEmpty() && !API_KEY.isEmpty() && !SECRET_KEY.isEmpty();
    }

    private static String baiduTextToSpeech(String text, String filePath) {
        try {
            AipSpeech speechClient = getClient();
            if (speechClient == null) {
                lastError = "未配置百度语音密钥（BAIDU_TTS_APP_ID / BAIDU_TTS_API_KEY / BAIDU_TTS_SECRET_KEY）。";
                return "";
            }

            List<String> textChunks = splitText(text, 500);
            if (textChunks.isEmpty()) {
                lastError = "无有效文本可合成";
                return "";
            }

            ByteArrayOutputStream allAudio = new ByteArrayOutputStream();
            boolean firstChunk = true;

            for (String chunk : textChunks) {
                if (chunk.trim().isEmpty()) continue;

                HashMap<String, Object> options = new HashMap<>();
                // 略慢于默认，课堂口播更自然
                options.put("spd", "4");
                options.put("pit", "5");
                options.put("vol", "15");
                options.put("per", "4");

                TtsResponse res = speechClient.synthesis(chunk, "zh", 1, options);
                JSONObject result = res.getResult();

                if (result == null) {
                    if (!firstChunk) {
                        allAudio.write(new byte[]{0, 0, 0, 0});
                    }
                    allAudio.write(res.getData());
                    firstChunk = false;
                } else {
                    lastError = "百度语音接口返回失败：" + result.toString();
                    return "";
                }
            }

            Path out = Paths.get(filePath);
            Files.createDirectories(out.getParent());
            Util.writeBytesToFileSystem(allAudio.toByteArray(), filePath);
            return filePath;
        } catch (Exception e) {
            lastError = "百度语音异常：" + e.getMessage();
            return "";
        }
    }

    private static String edgeTextToSpeech(String text, String filePath, String voiceStyle) {
        try {
            Path script = resolveFreeTtsScript();
            if (script == null) {
                lastError = "未找到 tools/free_tts.py";
                return "";
            }
            Path python = resolvePython();
            if (python == null) {
                lastError = "未找到可用于 Edge TTS 的 Python（可配置 FREE_TTS_PYTHON）";
                return "";
            }

            Path out = Paths.get(filePath);
            Files.createDirectories(out.getParent() != null ? out.getParent() : Paths.get("."));
            Path textFile = Files.createTempFile("lecture-tts-", ".txt");
            Files.write(textFile, text.getBytes(StandardCharsets.UTF_8));

            List<String> cmd = new ArrayList<>();
            cmd.add(python.toAbsolutePath().toString());
            cmd.add(script.toAbsolutePath().toString());
            cmd.add("--text-file");
            cmd.add(textFile.toAbsolutePath().toString());
            cmd.add("--out");
            cmd.add(out.toAbsolutePath().toString());
            cmd.add("--voice");
            cmd.add(voiceStyle == null ? "soft_female" : voiceStyle.trim());

            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.redirectErrorStream(true);
            Process process = pb.start();
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append('\n');
                }
            }
            boolean finished = process.waitFor(180, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                lastError = "免费 Edge TTS 超时";
                Files.deleteIfExists(textFile);
                return "";
            }
            Files.deleteIfExists(textFile);
            int code = process.exitValue();
            if (code != 0 || !Files.isRegularFile(out) || Files.size(out) < 32) {
                String detail = output.toString().trim();
                lastError = "免费 Edge TTS 失败" + (detail.isEmpty() ? "" : "：" + detail);
                return "";
            }
            lastError = "";
            return out.toAbsolutePath().toString();
        } catch (Exception e) {
            lastError = "免费 Edge TTS 异常：" + e.getMessage();
            return "";
        }
    }

    private static String windowsSapiToWav(String text, String wavPath) {
        Path textFile = null;
        Path ps1 = null;
        Path tempWav = null;
        try {
            Path out = Paths.get(wavPath).toAbsolutePath().normalize();
            Files.createDirectories(out.getParent() != null ? out.getParent() : Paths.get("."));

            // PowerShell -File 默认按系统 ANSI 读脚本；中文绝对路径嵌入脚本会被读乱，
            // SetOutputToWaveFile 就会报 DirectoryNotFoundException。先写到 Temp（ASCII）再搬回。
            textFile = Files.createTempFile("lecture-sapi-", ".txt");
            Files.write(textFile, text.getBytes(StandardCharsets.UTF_8));
            tempWav = Files.createTempFile("lecture-sapi-out-", ".wav");
            Files.deleteIfExists(tempWav);

            String textEsc = textFile.toAbsolutePath().toString().replace("'", "''");
            String wavEsc = tempWav.toAbsolutePath().toString().replace("'", "''");
            String script = ""
                    + "$ErrorActionPreference='Stop'\n"
                    + "Add-Type -AssemblyName System.Speech\n"
                    + "$text = Get-Content -LiteralPath '" + textEsc + "' -Raw -Encoding UTF8\n"
                    + "$outWav = '" + wavEsc + "'\n"
                    + "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
                    + "try {\n"
                    + "  $zh = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh*' } | Select-Object -First 1\n"
                    + "  if ($zh) { $synth.SelectVoice($zh.VoiceInfo.Name) }\n"
                    + "  $synth.Rate = -2\n"
                    + "  $synth.Volume = 100\n"
                    + "  $synth.SetOutputToWaveFile($outWav)\n"
                    + "  $synth.Speak($text)\n"
                    + "} finally { $synth.Dispose() }\n";

            ps1 = Files.createTempFile("lecture-sapi-", ".ps1");
            // UTF-8 BOM，避免 Windows PowerShell 5.x 把脚本当系统代码页解析
            byte[] bom = new byte[]{(byte) 0xEF, (byte) 0xBB, (byte) 0xBF};
            byte[] body = script.getBytes(StandardCharsets.UTF_8);
            byte[] withBom = new byte[bom.length + body.length];
            System.arraycopy(bom, 0, withBom, 0, bom.length);
            System.arraycopy(body, 0, withBom, bom.length, body.length);
            Files.write(ps1, withBom);

            List<String> cmd = new ArrayList<>();
            cmd.add("powershell");
            cmd.add("-NoProfile");
            cmd.add("-ExecutionPolicy");
            cmd.add("Bypass");
            cmd.add("-File");
            cmd.add(ps1.toAbsolutePath().toString());

            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.redirectErrorStream(true);
            Process process = pb.start();
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append('\n');
                }
            }
            boolean finished = process.waitFor(180, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                lastError = "Windows 朗读超时";
                return "";
            }
            if (process.exitValue() != 0 || !Files.isRegularFile(tempWav) || Files.size(tempWav) < 32) {
                String detail = output.toString().trim();
                lastError = "Windows 朗读失败" + (detail.isEmpty() ? "（可能未安装中文语音包）" : "：" + detail);
                return "";
            }
            Files.copy(tempWav, out, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            lastError = "";
            return out.toString();
        } catch (Exception e) {
            lastError = "Windows 朗读异常：" + e.getMessage();
            return "";
        } finally {
            try {
                if (ps1 != null) {
                    Files.deleteIfExists(ps1);
                }
                if (textFile != null) {
                    Files.deleteIfExists(textFile);
                }
                if (tempWav != null) {
                    Files.deleteIfExists(tempWav);
                }
            } catch (Exception ignored) {
                // best-effort cleanup
            }
        }
    }

    private static String toWavPath(String filePath) {
        String p = filePath.trim();
        if (p.toLowerCase().endsWith(".mp3")) {
            return p.substring(0, p.length() - 4) + ".wav";
        }
        if (p.toLowerCase().endsWith(".wav")) {
            return p;
        }
        return p + ".wav";
    }

    private static Path resolveFreeTtsScript() {
        List<Path> candidates = new ArrayList<>();
        String configured = System.getenv("FREE_TTS_SCRIPT");
        if (configured != null && !configured.trim().isEmpty()) {
            candidates.add(Paths.get(configured.trim()));
        }
        Path cwd = Paths.get("").toAbsolutePath();
        candidates.add(cwd.resolve("tools").resolve("free_tts.py"));
        candidates.add(cwd.resolve("ai-teacher").resolve("tools").resolve("free_tts.py"));
        // 兼容从 IDE 以模块目录启动
        candidates.add(Paths.get(System.getProperty("user.dir", ".")).resolve("tools").resolve("free_tts.py"));
        for (Path p : candidates) {
            if (p != null && Files.isRegularFile(p)) {
                return p.toAbsolutePath().normalize();
            }
        }
        return null;
    }

    private static Path resolvePython() {
        List<Path> candidates = new ArrayList<>();
        String configured = System.getenv("FREE_TTS_PYTHON");
        if (configured != null && !configured.trim().isEmpty()) {
            candidates.add(Paths.get(configured.trim()));
        }
        String zhixuetiPy = System.getenv("ZHIXUETI_PYTHON_EXE");
        if (zhixuetiPy != null && !zhixuetiPy.trim().isEmpty()) {
            candidates.add(Paths.get(zhixuetiPy.trim()));
        }
        candidates.add(Paths.get("D:\\Code\\software\\A3_V19\\backend\\venv\\Scripts\\python.exe"));
        Path cwd = Paths.get("").toAbsolutePath();
        candidates.add(cwd.resolve("tools").resolve("tts-venv").resolve("Scripts").resolve("python.exe"));
        candidates.add(cwd.resolve("zhixueti-backend").resolve("venv").resolve("Scripts").resolve("python.exe"));
        for (Path p : candidates) {
            if (p != null && Files.isRegularFile(p)) {
                return p.toAbsolutePath().normalize();
            }
        }
        return null;
    }

    private static List<String> splitText(String text, int maxLen) {
        List<String> chunks = new ArrayList<>();
        int currentPos = 0;
        int textLen = text.length();

        while (currentPos < textLen) {
            int end = findByteSafeEnd(text, currentPos, maxLen);
            if (end < textLen) {
                int splitPos = text.lastIndexOf('。', end);
                if (splitPos <= currentPos) {
                    splitPos = text.lastIndexOf('\n', end);
                }
                if (splitPos <= currentPos) {
                    splitPos = text.lastIndexOf('，', end);
                }
                if (splitPos > currentPos) {
                    end = splitPos + 1;
                }
            }
            chunks.add(text.substring(currentPos, end));
            currentPos = end;
        }
        return chunks;
    }

    private static int findByteSafeEnd(String text, int start, int maxBytes) {
        int end = start;
        int bytes = 0;
        while (end < text.length()) {
            int next = text.offsetByCodePoints(end, 1);
            int charBytes = text.substring(end, next).getBytes(StandardCharsets.UTF_8).length;
            if (bytes + charBytes > maxBytes) {
                break;
            }
            bytes += charBytes;
            end = next;
        }
        return end > start ? end : text.offsetByCodePoints(start, 1);
    }

    private static synchronized AipSpeech getClient() {
        if (client != null) {
            return client;
        }
        if (!hasBaiduKeys()) {
            return null;
        }
        client = new AipSpeech(APP_ID, API_KEY, SECRET_KEY);
        client.setConnectionTimeoutInMillis(5000);
        client.setSocketTimeoutInMillis(60000);
        return client;
    }

    private static String env(String primary, String fallback) {
        String value = System.getenv(primary);
        if (value == null || value.trim().isEmpty()) {
            value = System.getenv(fallback);
        }
        return value == null ? "" : value.trim();
    }

    public static String generateDigitalHumanHtml(String script, String audioUrl) {
        String safeScript = escapeHtml(script);
        String safeAudioUrl = escapeHtml(audioUrl);
        String avatarUrl = "/images/digital-human/teacher-avatar-v2.png";
        boolean wav = safeAudioUrl.toLowerCase().contains(".wav");
        String audioType = wav ? "audio/wav" : "audio/mpeg";
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html>")
                .append("<html lang='zh-CN'>")
                .append("<head>")
                .append("<meta charset='UTF-8'>")
                .append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
                .append("<title>AI数字人讲课</title>")
                .append("<style>")
                .append("*{margin:0;padding:0;box-sizing:border-box;font-family:'PingFang SC','Microsoft YaHei',sans-serif;}")
                .append("body{background:radial-gradient(circle at 20% 20%,#edf6ff,#f6fbff 45%,#eef3ff 100%);padding:20px;color:#1f2a44;}")
                .append(".container{max-width:1200px;margin:0 auto;}")
                .append("h2{font-size:36px;text-align:center;color:#1f5eff;letter-spacing:1px;margin-bottom:18px;}")
                .append(".grid{display:grid;grid-template-columns:360px 1fr;gap:20px;align-items:stretch;}")
                .append(".card{background:#fff;border:1px solid #e7ebf5;border-radius:18px;box-shadow:0 10px 30px rgba(31,94,255,.08);}")
                .append(".avatar-card{padding:18px;position:relative;overflow:hidden;background:linear-gradient(180deg,#ffffff,#f3f8ff);}")
                .append(".avatar-card::before{content:'';position:absolute;inset:-90px -50px auto auto;width:240px;height:240px;background:radial-gradient(circle,#7eb6ff66,transparent 70%);}")
                .append(".avatar-stage{position:relative;width:100%;height:420px;border-radius:16px;overflow:hidden;background:linear-gradient(180deg,#eaf6ff,#f7fbff);border:1px solid #dce8ff;box-shadow:inset 0 0 40px rgba(73,139,255,.10);}")
                .append(".avatar-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center top;transform-origin:center 72%;transition:transform .16s ease-out;}")
                .append(".aura{position:absolute;inset:0;background:radial-gradient(circle at 50% 35%,rgba(255,255,255,.18),transparent 38%),linear-gradient(180deg,transparent 58%,rgba(24,88,204,.16));pointer-events:none;}")
                .append(".avatar-label{position:absolute;left:14px;right:14px;bottom:14px;padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.82);backdrop-filter:blur(10px);border:1px solid rgba(220,232,255,.9);color:#26426f;font-size:13px;font-weight:700;display:flex;justify-content:space-between;gap:10px;}")
                .append(".status{margin-top:12px;padding:10px 12px;border-radius:10px;background:#eef4ff;color:#3e5fb6;font-size:14px;}")
                .append(".audio-card{padding:20px;display:flex;flex-direction:column;gap:12px;}")
                .append(".title{font-size:20px;font-weight:700;color:#233b77;}")
                .append(".btn{border:none;border-radius:10px;padding:10px 14px;background:linear-gradient(135deg,#2d7eff,#4f98ff);color:#fff;cursor:pointer;font-weight:700;width:140px;}")
                .append(".btn:disabled{opacity:.55;cursor:not-allowed;}")
                .append("audio{width:100%;}")
                .append(".hint{font-size:13px;color:#5d6f9e;}")
                .append(".script{margin-top:18px;padding:20px;line-height:1.9;font-size:16px;}")
                .append("pre{white-space:pre-wrap;word-break:break-word;}")
                .append("@media (max-width:900px){h2{font-size:30px;}.grid{grid-template-columns:1fr;}.avatar-stage{height:460px;}}")
                .append("</style>")
                .append("</head>")
                .append("<body>")
                .append("<div class='container'>")
                .append("<h2>AI数字人讲课助手</h2>")
                .append("<div class='grid'>")
                .append("<div class='card avatar-card'>")
                .append("<div class='avatar-stage'>")
                .append("<img id='avatarImg' class='avatar-img' src='").append(avatarUrl).append("' alt='AI数字教师形象'>")
                .append("<div class='aura'></div>")
                .append("<div class='avatar-label'><span>AI数字教师</span><span>实时播报</span></div>")
                .append("</div>")
                .append("<div id='avatarStatus' class='status'>状态：等待播放</div>")
                .append("</div>")
                .append("<div class='card audio-card'>")
                .append("<div class='title'>语音播报</div>")
                .append("<button id='startBtn' class='btn'>开始播报</button>")
                .append("<audio id='voice' controls>")
                .append("<source src='").append(safeAudioUrl).append("' type='").append(audioType).append("'>")
                .append("你的浏览器不支持音频播放。")
                .append("</audio>")
                .append("<div class='hint'>嘴型、眨眼、点头会随声音动态联动。</div>")
                .append("</div>")
                .append("</div>")
                .append("<div class='card script'>")
                .append("<div class='title' style='margin-bottom:10px;'>讲课讲稿</div>")
                .append("<pre>").append(safeScript).append("</pre>")
                .append("</div>")
                .append("</div>")
                .append("<script>")
                .append("const audio=document.getElementById('voice');")
                .append("const startBtn=document.getElementById('startBtn');")
                .append("const statusEl=document.getElementById('avatarStatus');")
                .append("startBtn.addEventListener('click',async()=>{try{await audio.play();statusEl.textContent='状态：讲解中';startBtn.disabled=true;}catch(e){statusEl.textContent='状态：播放被浏览器拦截，请再次点击';}});")
                .append("audio.addEventListener('play',()=>{statusEl.textContent='状态：讲解中';startBtn.disabled=true;});")
                .append("audio.addEventListener('pause',()=>{if(!audio.ended){statusEl.textContent='状态：已暂停';startBtn.disabled=false;}});")
                .append("audio.addEventListener('ended',()=>{statusEl.textContent='状态：讲解完成';startBtn.disabled=false;});")
                .append("</script>")
                .append("</body>")
                .append("</html>");
        return html.toString();
    }

    private static String escapeHtml(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }
}
