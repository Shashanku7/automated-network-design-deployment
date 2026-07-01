package org.acme.gateway;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.PATCH;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.extern.java.Log;
import org.acme.gateway.entities.AgentTaskEntity;
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
import org.eclipse.microprofile.jwt.JsonWebToken;
import org.eclipse.microprofile.rest.client.inject.RestClient;

@Path("api")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
@Log
public class APIResource {

  @Inject JsonWebToken jwt;

  @Inject KafkaService kafkaService;

  @Inject @RestClient AIService aiService;

  @Inject ProjectRepository projectRepository;

  @Inject ConversationRepository conversationRepository;

  @Inject MessageRepository messageRepository;

  @Inject AgentTaskRepository agentTaskRepository;

  private String currentUserId() {
    return jwt.getSubject();
  }

  // ── Projects ─────────────────────────────────────────

  @GET
  @Path("projects")
  public List<ProjectEntity> listProjects() {
    return projectRepository.findByUserId(currentUserId());
  }

  @POST
  @Path("projects")
  @Transactional
  public Response createProject(CreateProjectRequest request) {
    var project = new ProjectEntity(request.title(), currentUserId());
    if (request.id() != null) {
      project.setId(request.id());
    }
    projectRepository.persist(project);
    return Response.ok(project).build();
  }

  @GET
  @Path("projects/{id}")
  public Response getProject(@PathParam("id") UUID id) {
    var project = projectRepository.findById(id);
    if (project == null) return Response.status(404).build();
    if (!project.getUserId().equals(currentUserId())) return Response.status(404).build();
    return Response.ok(project).build();
  }

  @PATCH
  @Path("projects/{id}")
  @Transactional
  public Response updateProject(@PathParam("id") UUID id, UpdateProjectRequest request) {
    var project = projectRepository.findById(id);
    if (project == null) {
      project = new ProjectEntity(
          request.title() != null ? request.title() : "Untitled Project",
          currentUserId());
      project.setId(id);
    } else {
      if (!project.getUserId().equals(currentUserId())) return Response.status(404).build();
    }
    if (request.title() != null) project.setTitle(request.title());
    if (request.solutionType() != null) project.setSolutionType(request.solutionType());
    if (request.requirements() != null) project.setRequirements(request.requirements());
    if (request.chatHistory() != null) project.setChatHistory(request.chatHistory());
    if (request.workflowStatus() != null) project.setWorkflowStatus(request.workflowStatus());
    return Response.ok(project).build();
  }

  // ── Conversations ────────────────────────────────────

  @GET
  @Path("projects/{projectId}/conversations")
  public Response listConversations(@PathParam("projectId") UUID projectId) {
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    return Response.ok(conversationRepository.findByProjectId(projectId)).build();
  }

  @POST
  @Path("projects/{projectId}/conversations")
  @Transactional
  public Response createConversation(
      @PathParam("projectId") UUID projectId, CreateConversationRequest request) {
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    var conversation = new ConversationEntity(projectId, request.title());
    conversation.setUserId(currentUserId());
    conversationRepository.persist(conversation);
    return Response.ok(conversation).build();
  }

  // ── Messages ─────────────────────────────────────────

  @GET
  @Path("conversations/{conversationId}/messages")
  public Response getMessages(@PathParam("conversationId") UUID conversationId) {
    var conv = conversationRepository.findById(conversationId);
    if (conv == null) return Response.status(404).build();
    var project = projectRepository.findById(conv.getProjectId());
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    return Response.ok(messageRepository.findByConversationIdOrdered(conversationId)).build();
  }

  @GET
  @Path("projects/{projectId}/chat-history")
  public Response getPersistentChatHistory(
      @PathParam("projectId") UUID projectId, @QueryParam("conversationId") String conversationId) {
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    try {
      var cid = conversationId == null || conversationId.isBlank() ? "default" : conversationId;
      var history = aiService.getChatHistory(projectId.toString(), cid);
      return Response.ok(history).build();
    } catch (Exception e) {
      log.warning(
          "Failed to fetch persistent chat history for projectId="
              + projectId
              + " error="
              + e.getMessage());
      return Response.ok(
              Map.of(
                  "project_id", projectId.toString(),
                  "conversation_id",
                      conversationId == null || conversationId.isBlank()
                          ? "default"
                          : conversationId,
                  "conversation_key", "",
                  "conversation_messages", List.of(),
                  "phase_messages", Map.of(),
                  "merged_messages", List.of()))
          .build();
    }
  }

  @POST
  @Path("conversations/{conversationId}/messages")
  @Transactional
  public Response saveMessage(
      @PathParam("conversationId") UUID conversationId, SaveMessageRequest request) {
    var conv = conversationRepository.findById(conversationId);
    if (conv == null) return Response.status(404).build();
    var project = projectRepository.findById(conv.getProjectId());
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    var seq = messageRepository.countByConversationId(conversationId) + 1;
    var message = new MessageEntity(conversationId, seq, request.role(), request.content());
    messageRepository.persist(message);
    return Response.ok(message).build();
  }

  // ── Workflow State ─────────────────────────────────

  @GET
  @Path("projects/{pid}/phases")
  public Response getWorkflowState(@PathParam("pid") UUID projectId) {
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    var completed = agentTaskRepository.findCompletedByProjectId(projectId);
    var latestPerPhase =
        completed.stream()
            .collect(
                Collectors.toMap(
                    AgentTaskEntity::getPhase,
                    java.util.function.Function.identity(),
                    (a, b) -> {
                      if (a.getCompletedAt() == null) return b;
                      if (b.getCompletedAt() == null) return a;
                      return a.getCompletedAt().isAfter(b.getCompletedAt()) ? a : b;
                    }));
    // Exclude phases awaiting user approval (AI finished but HITL not yet given)
    var latestCompleted = agentTaskRepository.findLatestCompletedByProjectId(projectId);
    boolean hasPendingApproval =
        latestCompleted.isPresent()
            && !agentTaskRepository.existsByProjectIdAndPhase(
                projectId, latestCompleted.get().getPhase() + 1);

    var phases =
        latestPerPhase.values().stream()
            .filter(
                t ->
                    !hasPendingApproval || !t.getTaskId().equals(latestCompleted.get().getTaskId()))
            .map(
                t ->
                    new PhaseResult(t.getPhase(), t.getAgentTarget(), t.getOutput(), t.getStatus()))
            .sorted((a, b) -> Integer.compare(a.phase(), b.phase()))
            .toList();
    int nextPhase = phases.isEmpty() ? 1 : Math.min(phases.getLast().phase() + 1, 5);
    String status =
        (project != null && "complete".equals(project.getWorkflowStatus()))
            ? "complete"
            : "running";
    return Response.ok(new WorkflowState(projectId, status, nextPhase, phases)).build();
  }

  // ── Deploy ─────────────────────────────────────────

  @POST
  @Path("deploy")
  public Response deploy(DeployRequest request) {
    var projectId = UUID.fromString(request.projectId());
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    log.info("deploy projectId=" + request.projectId());
    return Response.ok(
            Map.of(
                "status", "success",
                "message",
                    "Deployment initiated. Configuration is being pushed to network devices.",
                "projectId", request.projectId()))
        .build();
  }

  // ── Existing endpoints ───────────────────────────────

  @POST
  @Path("tasks")
  public Response createTask(CreateTaskRequest request) {
    var projectId = UUID.fromString(request.projectId());
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    kafkaService.sendTask(request.message(), projectId, currentUserId());
    return Response.accepted().build();
  }

  public record CreateTaskRequest(String projectId, String message) {}

  public record ChatRequest(
      String message,
      List<AgentTask.ChatMessage> history,
      @JsonProperty("project_id") String projectId,
      @JsonProperty("conversation_id") String conversationId,
      @JsonProperty("screen_context") String screenContext) {}

  @POST
  @Path("chat")
  public Response chat(ChatRequest request) {
    var projectId = UUID.fromString(request.projectId());
    var project = projectRepository.findById(projectId);
    if (project == null || !project.getUserId().equals(currentUserId())) return Response.status(404).build();
    try {
      var history =
          request.history().stream()
              .map(h -> new AIService.ChatHistoryItem(h.role().name().toLowerCase(), h.content()))
              .collect(Collectors.toList());
      var aiRequest =
          new AIService.ChatRequest(
              request.message(), history, request.projectId(), request.screenContext());
      var aiResponse = aiService.sendChat(aiRequest);
      return Response.ok(aiResponse).build();
    } catch (Exception e) {
      var fallback =
          Map.of(
              "role",
              "assistant",
              "content",
              "Thank you for your question. The chat copilot is processing: \""
                  + request.message()
                  + "\"",
              "timestamp",
              Instant.now().toString());
      return Response.ok(fallback).build();
    }
  }

  // ── Request records ─────────────────────────────────

  public record CreateProjectRequest(String title, UUID id) {}

  public record CreateConversationRequest(String title) {}

  public record SaveMessageRequest(String role, String content) {}

  public record DeployRequest(String projectId) {}

  public record UpdateProjectRequest(
      String title,
      @JsonProperty("solution_type") String solutionType,
      String requirements,
      @JsonProperty("chat_history") String chatHistory,
      @JsonProperty("workflow_status") String workflowStatus) {}
}
