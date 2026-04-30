package app.marysia.skel.controller;

import app.marysia.skel.model.Item;
import app.marysia.skel.service.ItemService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:itemtest;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa",
    "spring.datasource.password="
})
class ItemControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ItemService itemService;

    @Autowired
    private ObjectMapper objectMapper;

    /** Register + login, return the access token. */
    private String obtainAccessToken() throws Exception {
        String username = "test-" + UUID.randomUUID().toString().substring(0, 8);
        String body = """
            { "username": "%s", "email": "%s@test.com", "password": "pass1234" }
            """.formatted(username, username);

        mockMvc.perform(post("/api/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated());

        MvcResult login = mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "username": "%s", "password": "pass1234" }
                    """.formatted(username)))
            .andExpect(status().isOk())
            .andReturn();

        JsonNode json = objectMapper.readTree(login.getResponse().getContentAsString());
        return json.path("access").asText();
    }

    @Test
    void getAllItems_ReturnsItemsList() throws Exception {
        Item item = new Item(1L, "Test Item", "Description", false, null, "2026-01-01T00:00:00", null);
        when(itemService.findAll()).thenReturn(List.of(item));

        String token = obtainAccessToken();
        mockMvc.perform(get("/api/items")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].name").value("Test Item"));
    }

    @Test
    void getItemById_WhenExists_ReturnsItem() throws Exception {
        Item item = new Item(1L, "Test Item", "Description", false, null, "2026-01-01T00:00:00", null);
        when(itemService.findById(1L)).thenReturn(Optional.of(item));

        String token = obtainAccessToken();
        mockMvc.perform(get("/api/items/1")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("Test Item"));
    }

    @Test
    void getItemById_WhenNotExists_ReturnsNotFound() throws Exception {
        when(itemService.findById(1L)).thenReturn(Optional.empty());

        String token = obtainAccessToken();
        mockMvc.perform(get("/api/items/1")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isNotFound());
    }

    @Test
    void createItem_ReturnsCreatedItem() throws Exception {
        Item created = new Item(1L, "New Item", "Description", false, null, "2026-01-01T00:00:00", null);
        when(itemService.create(anyString(), anyString(), anyBoolean(), any())).thenReturn(created);

        String token = obtainAccessToken();
        mockMvc.perform(post("/api/items")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    { "name": "New Item", "description": "Description" }
                    """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("New Item"));
    }

    @Test
    void anonymousRequest_ReturnsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/items"))
            .andExpect(status().isUnauthorized());
    }
}
