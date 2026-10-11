package com.contest;

import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;

@Configuration
public class StaticResourceConfig implements WebMvcConfigurer {

    @Value("${app.cors.allowed-origins:}")
    private String allowedOrigins;

    @Value("${app.cors.allowed-methods:GET,POST,PUT,DELETE,OPTIONS}")
    private String allowedMethods;

    @Value("${app.cors.allowed-headers:*}")
    private String allowedHeaders;

    @Value("${app.generated-static-dir:data/generated-static}")
    private String generatedStaticDir;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        Path reportsPath = Paths.get("reports").toAbsolutePath().normalize();
        String location = reportsPath.toUri().toString();
        registry.addResourceHandler("/reports/**")
                .addResourceLocations(location);

        String[] generatedStaticLocations = generatedStaticLocations();
        registry.addResourceHandler("/digital-human-*.html")
                .addResourceLocations(generatedStaticLocations);
        // /audio/foo.wav → {generated-static}/audio/foo.wav （文件写在 audio 子目录）
        registry.addResourceHandler("/audio/**")
                .addResourceLocations(generatedAudioLocations());
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        String[] origins = splitCsv(allowedOrigins);
        if (origins.length == 0) {
            return;
        }
        registry.addMapping("/**")
                .allowedOrigins(origins)
                .allowedMethods(splitCsv(allowedMethods))
                .allowedHeaders(splitCsv(allowedHeaders))
                .allowCredentials(true)
                .maxAge(3600);
    }

    private String[] splitCsv(String value) {
        if (value == null || value.trim().isEmpty()) {
            return new String[0];
        }
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(item -> !item.isEmpty())
                .toArray(String[]::new);
    }

    private String[] generatedStaticLocations() {
        List<String> locations = new ArrayList<>();
        locations.add(Paths.get(generatedStaticDir == null || generatedStaticDir.trim().isEmpty()
                        ? "data/generated-static"
                        : generatedStaticDir.trim())
                .toAbsolutePath()
                .normalize()
                .toUri()
                .toString());
        locations.add(Paths.get("target/classes/static").toAbsolutePath().normalize().toUri().toString());
        locations.add(Paths.get("src/main/resources/static").toAbsolutePath().normalize().toUri().toString());
        return locations.toArray(new String[0]);
    }

    private String[] generatedAudioLocations() {
        List<String> locations = new ArrayList<>();
        Path root = Paths.get(generatedStaticDir == null || generatedStaticDir.trim().isEmpty()
                        ? "data/generated-static"
                        : generatedStaticDir.trim())
                .toAbsolutePath()
                .normalize();
        locations.add(root.resolve("audio").toUri().toString());
        // 兼容误写在 generated-static 根目录的旧文件
        locations.add(root.toUri().toString());
        return locations.toArray(new String[0]);
    }
}
