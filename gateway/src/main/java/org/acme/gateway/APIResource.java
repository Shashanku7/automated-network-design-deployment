package org.acme.gateway;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.services.AIService;
import org.acme.gateway.services.KafkaService;
import org.eclipse.microprofile.rest.client.inject.RestClient;

@Path("api")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class APIResource {

  @Inject
  KafkaService kafkaService;

  @Inject
  @RestClient
  AIService aiService;

  @POST
  @Path("tasks")
  public Response createTask(CreateTaskRequest request) {
    kafkaService.sendTask(request.message(), UUID.fromString(request.projectId()));

    return Response.accepted().build();
  }

  public record CreateTaskRequest(String projectId, String message) {
  }

  public record ChatRequest(String message, List<AgentTask.ChatMessage> history) {
  }

  @POST
  @Path("chat")
  public Response chat(ChatRequest request) {
    try {
      var history = request.history().stream()
          .map(h -> new AIService.ChatHistoryItem(
              h.role().name().toLowerCase(),
              h.content()))
          .collect(Collectors.toList());
      var aiRequest = new AIService.ChatRequest(request.message(), history);
      var aiResponse = aiService.sendChat(aiRequest);
      return Response.ok(aiResponse).build();
    } catch (Exception e) {
      var fallback = Map.of(
          "role", "assistant",
          "content", "Thank you for your question. The chat copilot is processing: \"" + request.message() + "\"",
          "timestamp", Instant.now().toString());
      return Response.ok(fallback).build();
    }
  }
}
