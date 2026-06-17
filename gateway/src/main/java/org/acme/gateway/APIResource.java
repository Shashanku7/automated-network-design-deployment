package org.acme.gateway;

import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.acme.gateway.entities.ConversationEntity;
import org.acme.gateway.entities.MessageEntity;
import org.acme.gateway.entities.ProjectEntity;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.models.PhaseResult;
import org.acme.gateway.models.WorkflowState;
import org.acme.gateway.repositories.AgentTaskRepository;
import org.acme.gateway.repositories.ConversationRepository;
import org.acme.gateway.repositories.MessageRepository;
import org.acme.gateway.repositories.ProjectRepository;
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

  @Inject
  ProjectRepository projectRepository;

  @Inject
  ConversationRepository conversationRepository;

  @Inject
  MessageRepository messageRepository;

  @Inject
  AgentTaskRepository agentTaskRepository;

  // ── Projects ─────────────────────────────────────────

  @GET
  @Path("projects")
  public List<ProjectEntity> listProjects() {
    return projectRepository.listAll();
  }

  @POST
  @Path("projects")
  @Transactional
  public Response createProject(CreateProjectRequest request) {
    var project = new ProjectEntity(request.title());
    projectRepository.persist(project);
    return Response.ok(project).build();
  }

  @GET
  @Path("projects/{id}")
  public Response getProject(@PathParam("id") UUID id) {
    var project = projectRepository.findById(id);
    if (project == null) return Response.status(404).build();
    return Response.ok(project).build();
  }

  // ── Conversations ────────────────────────────────────

  @GET
  @Path("projects/{projectId}/conversations")
  public List<ConversationEntity> listConversations(@PathParam("projectId") UUID projectId) {
    return conversationRepository.findByProjectId(projectId);
  }

  @POST
  @Path("projects/{projectId}/conversations")
  @Transactional
  public Response createConversation(@PathParam("projectId") UUID projectId, CreateConversationRequest request) {
    var conversation = new ConversationEntity(projectId, request.title());
    conversationRepository.persist(conversation);
    return Response.ok(conversation).build();
  }

  // ── Messages ─────────────────────────────────────────

  @GET
  @Path("conversations/{conversationId}/messages")
  public List<MessageEntity> getMessages(@PathParam("conversationId") UUID conversationId) {
    return messageRepository.findByConversationIdOrdered(conversationId);
  }

  @POST
  @Path("conversations/{conversationId}/messages")
  @Transactional
  public Response saveMessage(@PathParam("conversationId") UUID conversationId, SaveMessageRequest request) {
    var seq = messageRepository.countByConversationId(conversationId) + 1;
    var message = new MessageEntity(conversationId, seq, request.role(), request.content());
    messageRepository.persist(message);
    return Response.ok(message).build();
  }

  // ── Workflow State ─────────────────────────────────

  @GET
  @Path("projects/{pid}/phases")
  public Response getWorkflowState(@PathParam("pid") UUID projectId) {
    var completed = agentTaskRepository.findCompletedByProjectId(projectId);
    var phases = completed.stream()
        .map(t -> new PhaseResult(t.getPhase(), t.getAgentTarget(), t.getOutput(), t.getStatus()))
        .toList();
    int nextPhase = completed.isEmpty() ? 1
        : Math.min(completed.getLast().getPhase() + 1, 6);
    return Response.ok(new WorkflowState(projectId,
        nextPhase > 5 ? "complete" : "running", nextPhase, phases)).build();
  }

  // ── Existing endpoints ───────────────────────────────

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

  // ── Request records ─────────────────────────────────

  public record CreateProjectRequest(String title) {
  }

  public record CreateConversationRequest(String title) {
  }

  public record SaveMessageRequest(String role, String content) {
  }
}
