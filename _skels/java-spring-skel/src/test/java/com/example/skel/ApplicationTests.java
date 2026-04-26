package com.example.skel;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Smoke test for the wrapper-shared backend stack.
 *
 * <p>Brings up the full Spring context against an in-memory H2
 * database (the wrapper-shared {@code SPRING_DATASOURCE_URL} is
 * overridden via {@link TestPropertySource}) and exercises the
 * canonical {@code register → login → list → reject anonymous} flow
 * to prove that:
 *
 * <ul>
 *   <li>{@link com.example.skel.config.SchemaInitializer} created the
 *       wrapper-shared tables on startup.</li>
 *   <li>{@code /api/auth/*} handlers mint working JWTs.</li>
 *   <li>The JWT interceptor rejects anonymous requests with 401.</li>
 *   <li>The JWT interceptor accepts a freshly-minted access token.</li>
 * </ul>
 *
 * <p>This complements the cross-stack {@code skel-test-react-spring}
 * runner, which exercises the same flow over real HTTP. The unit
 * suite catches regressions much faster (no network, no Vite build).
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:smoke;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa",
    "spring.datasource.password="
})
class ApplicationTests {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper mapper;

    @Test
    void contextLoads() {
        // Spring context bootstrap is itself the assertion. If
        // SchemaInitializer or DataSourceConfig fail, this test fails
        // before any of the others run.
    }

    @Test
    void registerLoginListItemsFlow() throws Exception {
        String username = "smoke-" + UUID.randomUUID().toString().substring(0, 8);
        String registerBody = """
            {
              "username": "%s",
              "email":    "%s@example.com",
              "password": "smoke-password-1234"
            }
            """.formatted(username, username);

        MvcResult registered = mockMvc.perform(post("/api/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(registerBody))
            .andExpect(status().isCreated())
            .andReturn();
        JsonNode regJson = mapper.readTree(registered.getResponse().getContentAsString());
        assertTrue(regJson.has("user"), "register response must include user");
        assertTrue(regJson.path("user").has("id"), "user object must include id");
        assertTrue(regJson.has("access"), "register response must include access token");

        MvcResult loggedIn = mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "username": "%s", "password": "smoke-password-1234" }
                    """.formatted(username)))
            .andExpect(status().isOk())
            .andReturn();
        JsonNode loginJson = mapper.readTree(loggedIn.getResponse().getContentAsString());
        String accessToken = loginJson.path("access").asText();
        assertFalse(accessToken.isBlank(), "login response must contain a non-empty access token");

        // Anonymous /api/items is 401.
        mockMvc.perform(get("/api/items"))
            .andExpect(status().isUnauthorized());

        // /api/items with the freshly-minted token is 200.
        mockMvc.perform(get("/api/items")
                .header("Authorization", "Bearer " + accessToken))
            .andExpect(status().isOk());
    }

    @Test
    void invalidTokenIsRejected() throws Exception {
        mockMvc.perform(get("/api/items")
                .header("Authorization", "Bearer not-a-real-token"))
            .andExpect(status().isUnauthorized());
    }

    @Test
    void rootEndpointReturnsOk() throws Exception {
        mockMvc.perform(get("/"))
            .andExpect(status().isOk());
        // Root is unauthenticated by design — only /api/items and
        // /api/state are JWT-protected. This test pins that contract.
        assertEquals(0, 0); // sentinel — the assertion is the status check above
    }

    @Test
    void defaultUserCanLogin() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"user\", \"password\": \"secret\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.access").isNotEmpty());
    }

    @Test
    void defaultSuperuserCanLogin() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"admin\", \"password\": \"secret\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.access").isNotEmpty());
    }

    @Test
    void loginByEmail() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"user@example.com\", \"password\": \"secret\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.access").isNotEmpty());
    }

    @Test
    void loginByEmailSuperuser() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"admin@example.com\", \"password\": \"secret\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.access").isNotEmpty());
    }
}
