package app.marysia.skel;

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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
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
 *   <li>Hibernate's {@code ddl-auto=update} created the wrapper-shared
 *       tables on startup from the {@code @Entity} annotations.</li>
 *   <li>{@link app.marysia.skel.config.DefaultUserSeeder} populated the
 *       canonical {@code user}/{@code admin} default accounts.</li>
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
        // Spring context bootstrap is itself the assertion. If JPA fails
        // to bootstrap the schema or DataSourceConfig cannot resolve the
        // SQLite URL, this test fails before any of the others run.
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

    @Test
    void orderWorkflowFullLifecycle() throws Exception {
        // --- register a fresh user and grab the access token ---
        String username = "order-" + UUID.randomUUID().toString().substring(0, 8);
        MvcResult regResult = mockMvc.perform(post("/api/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "username": "%s", "email": "%s@example.com", "password": "order-pass-1234" }
                    """.formatted(username, username)))
            .andExpect(status().isCreated())
            .andReturn();
        String token = mapper.readTree(regResult.getResponse().getContentAsString())
            .path("access").asText();

        // --- catalog: anonymous is 401 ---
        mockMvc.perform(get("/api/catalog"))
            .andExpect(status().isUnauthorized());

        // --- create a catalog item ---
        MvcResult catResult = mockMvc.perform(post("/api/catalog")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "name": "Widget", "description": "A fine widget", "price": 9.99, "category": "parts" }
                    """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("Widget"))
            .andExpect(jsonPath("$.price").value(9.99))
            .andReturn();
        long catalogItemId = mapper.readTree(catResult.getResponse().getContentAsString())
            .path("id").asLong();

        // --- list catalog ---
        mockMvc.perform(get("/api/catalog")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].name").value("Widget"));

        // --- get single catalog item ---
        mockMvc.perform(get("/api/catalog/" + catalogItemId)
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("Widget"));

        // --- create a draft order ---
        MvcResult orderResult = mockMvc.perform(post("/api/orders")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.status").value("draft"))
            .andReturn();
        long orderId = mapper.readTree(orderResult.getResponse().getContentAsString())
            .path("id").asLong();

        // --- list orders ---
        mockMvc.perform(get("/api/orders")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].id").value(orderId));

        // --- add a line ---
        MvcResult lineResult = mockMvc.perform(post("/api/orders/" + orderId + "/lines")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "catalog_item_id": %d, "quantity": 3 }
                    """.formatted(catalogItemId)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.quantity").value(3))
            .andExpect(jsonPath("$.unit_price").value(9.99))
            .andReturn();
        long lineId = mapper.readTree(lineResult.getResponse().getContentAsString())
            .path("id").asLong();

        // --- get order (includes lines, address null) ---
        mockMvc.perform(get("/api/orders/" + orderId)
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.lines[0].quantity").value(3))
            .andExpect(jsonPath("$.address").isEmpty());

        // --- set address ---
        mockMvc.perform(put("/api/orders/" + orderId + "/address")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "street": "123 Main St", "city": "Springfield", "zip_code": "62701" }
                    """))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.street").value("123 Main St"));

        // --- submit fails without lines? add second line then delete first ---
        // delete the line
        mockMvc.perform(delete("/api/orders/" + orderId + "/lines/" + lineId)
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isNoContent());

        // submit with zero lines should fail
        mockMvc.perform(post("/api/orders/" + orderId + "/submit")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isBadRequest());

        // re-add a line
        mockMvc.perform(post("/api/orders/" + orderId + "/lines")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "catalog_item_id": %d, "quantity": 1 }
                    """.formatted(catalogItemId)))
            .andExpect(status().isCreated());

        // --- submit ---
        mockMvc.perform(post("/api/orders/" + orderId + "/submit")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("pending"));

        // --- cannot add lines to submitted order ---
        mockMvc.perform(post("/api/orders/" + orderId + "/lines")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "catalog_item_id": %d, "quantity": 1 }
                    """.formatted(catalogItemId)))
            .andExpect(status().isBadRequest());

        // --- approve ---
        mockMvc.perform(post("/api/orders/" + orderId + "/approve")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"wait_minutes\": 25, \"feedback\": \"Processing!\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("approved"))
            .andExpect(jsonPath("$.wait_minutes").value(25));
    }

    @Test
    void orderRejectFlow() throws Exception {
        // register a user and create an order for reject testing
        String username = "rej-" + UUID.randomUUID().toString().substring(0, 8);
        MvcResult regResult = mockMvc.perform(post("/api/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "username": "%s", "email": "%s@example.com", "password": "reject-pass-1234" }
                    """.formatted(username, username)))
            .andExpect(status().isCreated())
            .andReturn();
        String token = mapper.readTree(regResult.getResponse().getContentAsString())
            .path("access").asText();

        // create catalog item
        MvcResult catResult = mockMvc.perform(post("/api/catalog")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "name": "Gadget", "price": 5.0 }
                    """))
            .andExpect(status().isCreated())
            .andReturn();
        long catId = mapper.readTree(catResult.getResponse().getContentAsString())
            .path("id").asLong();

        // create order, add line, submit
        MvcResult orderResult = mockMvc.perform(post("/api/orders")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isCreated())
            .andReturn();
        long orderId = mapper.readTree(orderResult.getResponse().getContentAsString())
            .path("id").asLong();

        mockMvc.perform(post("/api/orders/" + orderId + "/lines")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "catalog_item_id": %d }
                    """.formatted(catId)))
            .andExpect(status().isCreated());

        mockMvc.perform(post("/api/orders/" + orderId + "/submit")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk());

        // reject with feedback
        mockMvc.perform(post("/api/orders/" + orderId + "/reject")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "feedback": "out of stock" }
                    """))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("rejected"))
            .andExpect(jsonPath("$.feedback").value("out of stock"));
    }

    @Test
    void catalogNotFoundReturns404() throws Exception {
        // login as default user
        MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"user\", \"password\": \"secret\"}"))
            .andExpect(status().isOk())
            .andReturn();
        String token = mapper.readTree(loginResult.getResponse().getContentAsString())
            .path("access").asText();

        mockMvc.perform(get("/api/catalog/99999")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isNotFound());
    }
}
