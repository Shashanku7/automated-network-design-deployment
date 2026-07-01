package org.acme.gateway;

import java.util.Map;
import java.util.UUID;
import java.util.Base64;
import java.util.concurrent.ConcurrentHashMap;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.websockets.next.OnClose;
import io.quarkus.websockets.next.OnOpen;
import io.quarkus.websockets.next.OnTextMessage;
import io.quarkus.websockets.next.PathParam;
import io.quarkus.websockets.next.WebSocket;
import io.quarkus.websockets.next.WebSocketConnection;
import io.smallrye.common.annotation.Blocking;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import lombok.extern.java.Log;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.repositories.ProjectRepository;
import org.acme.gateway.services.KafkaService;
import org.acme.gateway.services.PipelineManager;
import org.acme.gateway.services.WorkflowOrchestrator;

@WebSocket(path = "/chat/{projectId}")
@ApplicationScoped
@Log
public class APIWebSocket {
  @Inject
  KafkaService kafkaService;
  @Inject
  WorkflowOrchestrator orchestrator;
  @Inject
  ObjectMapper objectMapper;
  @Inject
  PipelineManager pipelineManager;
  @Inject
  ProjectRepository projectRepository;
  Map<UUID, WebSocketConnection> connections = new ConcurrentHashMap<>();
  Map<UUID, String> connectionUserIds = new ConcurrentHashMap<>();

  @OnOpen
  @Transactional
  public void onOpen(WebSocketConnection connection, @PathParam("projectId") String projectId) {
    log.info("WS open projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    // Replace any stale connection — ensures new WS receives messages
    var old = connections.put(uuid, connection);
    if (old != null && old != connection && old.isOpen()) {
      old.close().subscribe().with(v -> {}, f -> {});
    }
    pipelineManager.rehydrateFromDb(uuid);
    orchestrator.replayPendingApproval(uuid);
  }

  @OnClose
  public void onClose(WebSocketConnection closing, @PathParam("projectId") String projectId) {
    log.info("WS close projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    // Only remove if closing connection matches — prevents stale close from
    // wiping out a newer connection that replaced it in onOpen
    connections.remove(uuid, closing);
    connectionUserIds.remove(uuid);
  }

  @Blocking
  @OnTextMessage
  public void onMessage(String message, @PathParam("projectId") String projectId) {
    log.info("WS msg projectId=" + projectId + " len=" + message.length() + " preview=" + message.substring(0, Math.min(200, message.length())));
    var uuid = UUID.fromString(projectId);

    // Handle auth — first message must be {"type":"auth","token":"xxx"}
    if (!connectionUserIds.containsKey(uuid)) {
      handleAuth(message, uuid, projectId);
      return;
    }

    // Handle ping/keepalive messages
    try {
      var tree = objectMapper.readTree(message);
      if (tree.has("type") && "ping".equals(tree.get("type").asText())) {
        return;
      }
    } catch (Exception e) {
      // fall through
    }

    // Check for approval/revision messages
    try {
      var tree = objectMapper.readTree(message);
      if (tree.has("approved")) {
        var approved = tree.get("approved").asBoolean();
        UUID taskId = tree.has("task_id") && !tree.get("task_id").isNull()
            ? UUID.fromString(tree.get("task_id").asText()) : null;
        Integer phase = tree.has("phase") && !tree.get("phase").isNull()
            ? tree.get("phase").asInt() : null;
        String feedback = approved ? null : tree.get("feedback").asText();
        if (!orchestrator.handleApproval(uuid, approved, feedback, taskId, phase)) {
          sendError(projectId, taskId, "Approval rejected or already processed.");
        }
        return;
      }
    } catch (Exception e) {
      if (message.contains("\"approved\"")) {
        sendError(projectId, null, "Invalid approval message format.");
        return;
      }
      // Not JSON or no approved field — treat as regular prompt
    }

    // Handle resume and restart
    try {
      var tree = objectMapper.readTree(message);
      if (tree.has("resume") && tree.get("resume").asBoolean()) {
        log.info("WS resume projectId=" + projectId);
        orchestrator.resumeWorkflow(uuid);
        return;
      }
      if (tree.has("restart") && tree.get("restart").asBoolean()) {
        log.info("WS restart projectId=" + projectId);
        orchestrator.restartWorkflow(uuid);
        // We will fall through to send the prompt to Kafka as a fresh task
      }
    } catch (Exception e) {
      // fall through
    }

    var userId = connectionUserIds.get(uuid);
    kafkaService.sendTask(message, uuid, userId);
  }

  private void handleAuth(String message, UUID uuid, String projectId) {
    try {
      var tree = objectMapper.readTree(message);
      if (!tree.has("type") || !"auth".equals(tree.get("type").asText()) || !tree.has("token")) {
        log.warning("WS auth fail projectId=" + projectId + " first msg not auth");
        return;
      }
      var token = tree.get("token").asText();
      var userId = extractUserId(token);
      if (userId == null) {
        log.warning("WS auth fail projectId=" + projectId + " bad token");
        return;
      }
      var project = projectRepository.findById(uuid);
      if (project == null || !userId.equals(project.getUserId())) {
        log.warning("WS auth fail projectId=" + projectId + " not owner");
        return;
      }
      connectionUserIds.put(uuid, userId);
      log.info("WS auth success projectId=" + projectId + " userId=" + userId);
    } catch (Exception e) {
      log.warning("WS auth fail projectId=" + projectId + " error=" + e.getMessage());
    }
  }

  public void sendMessage(String projectId, String content) {
    var uuid = UUID.fromString(projectId);
    WebSocketConnection connection = connections.get(uuid);
    if (connection != null) {
      log.info("WS send projectId=" + projectId + " len=" + content.length());
      connection.sendText(content).subscribe().with(v -> {});
    } else {
      log.warning("WS send fail projectId=" + projectId + " connection=null");
    }
  }

  private String extractUserId(String token) {
    try {
      var parts = token.split("\\.");
      if (parts.length != 3) return null;
      var payload = Base64.getUrlDecoder().decode(parts[1]);
      var json = objectMapper.readTree(payload);
      return json.get("sub").asText();
    } catch (Exception e) {
      return null;
    }
  }

  private void sendError(String projectId, UUID taskId, String message) {
    try {
      var event =
          new AgentEvent(
              UUID.fromString(projectId),
              taskId != null ? taskId : UUID.randomUUID(),
              "system",
              AgentEvent.EventType.ERROR,
              message,
              null,
              false,
              java.time.OffsetDateTime.now());
      sendMessage(projectId, objectMapper.writeValueAsString(event));
    } catch (Exception e) {
      log.severe("Failed to send WS error event: " + e.getMessage());
    }
  }
}
