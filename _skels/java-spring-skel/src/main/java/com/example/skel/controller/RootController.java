package com.example.skel.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class RootController {

    @Value("${spring.application.name:java-spring-skel}")
    private String projectName;

    @Value("${app.version:1.0.0}")
    private String version;

    @GetMapping("/")
    public Map<String, String> root() {
        return Map.of(
                "project", projectName,
                "version", version,
                "framework", "Spring Boot",
                "status", "running"
        );
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "healthy");
    }
}
