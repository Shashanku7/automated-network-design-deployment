package org.acme.gateway;

import java.util.Map;
import java.util.UUID;
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
import org.acme.gateway.services.KafkaService;
import org.acme.gateway.services.PipelineManager;

@WebSocket(path = "/chat/{projectId}")
@ApplicationScoped
@Log
public class APIWebSocket {
  @Inject
  KafkaService kafkaService;
  @Inject
  ObjectMapper objectMapper;
  @Inject
  PipelineManager pipelineManager;
  Map<UUID, WebSocketConnection> connections = new ConcurrentHashMap<>();

  @OnOpen
  @Transactional
  public void onOpen(WebSocketConnection connection, @PathParam("projectId") String projectId) {
    log.info("WS open projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    connections.putIfAbsent(uuid, connection);
    pipelineManager.rehydrateFromDb(uuid);
    kafkaService.replayPendingApproval(uuid);
  }

  @OnClose
  public void onClose(@PathParam("projectId") String projectId) {
    log.info("WS close projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    connections.remove(uuid);
  }

  @Blocking
  @OnTextMessage
  public void onMessage(String message, @PathParam("projectId") String projectId) {
    log.info("WS msg projectId=" + projectId + " len=" + message.length() + " preview=" + message.substring(0, Math.min(200, message.length())));
    var uuid = UUID.fromString(projectId);

    // Check for approval/revision messages
    try {
      var tree = objectMapper.readTree(message);
      if (tree.has("approved")) {
        var approved = tree.get("approved").asBoolean();
        UUID taskId = null;
        Integer phase = null;
        if (tree.has("task_id") && !tree.get("task_id").isNull()) {
          taskId = UUID.fromString(tree.get("task_id").asText());
        }
        if (tree.has("phase") && !tree.get("phase").isNull()) {
          phase = tree.get("phase").asInt();
        }
        var pending = kafkaService.getPendingApproval(uuid);
        if (pending.isEmpty()) {
          sendError(projectId, taskId, "No pending approval found for this project.");
          return;
        }
        var expected = pending.get();
        if (taskId == null || !expected.taskId().equals(taskId)) {
          sendError(projectId, taskId, "Approval task mismatch. Please refresh and retry.");
          return;
        }
        if (phase != null && phase > 0 && expected.phase() != phase) {
          sendError(projectId, taskId, "Approval phase mismatch. Please refresh and retry.");
          return;
        }
        if (!approved) {
          String feedback = tree.has("feedback") ? tree.get("feedback").asText() : "";
          if (feedback == null || feedback.trim().isEmpty()) {
            sendError(projectId, taskId, "Revision feedback cannot be empty.");
            return;
          }
          if (feedback.length() > 4000) {
            sendError(projectId, taskId, "Revision feedback is too long.");
            return;
          }
          if (!kafkaService.clearPendingApproval(uuid, taskId, phase)) {
            sendError(projectId, taskId, "Approval already processed.");
            return;
          }
        } else if (!kafkaService.clearPendingApproval(uuid, taskId, phase)) {
          sendError(projectId, taskId, "Approval already processed.");
          return;
        }
        log.info("WS approval msg projectId=" + projectId + " approved=" + approved);
        if (approved) {
          kafkaService.emitNextTask(uuid);
        } else {
          String feedback = tree.get("feedback").asText();
          log.info("WS revision msg projectId=" + projectId + " feedback=" + feedback);
          // Re-run current phase with feedback appended
          var state = pipelineManager.getOrCreateState(uuid);
          String lastOut = state.getLastOutput();
          String revisedInput = (lastOut != null ? lastOut : "") + "\n\n## Revision Request\n" + feedback;
          kafkaService.sendTask(revisedInput, uuid);
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
        kafkaService.resumeWorkflow(uuid);
        return;
      }
      if (tree.has("restart") && tree.get("restart").asBoolean()) {
        log.info("WS restart projectId=" + projectId);
        kafkaService.restartWorkflow(uuid);
        // We will fall through to send the prompt to Kafka as a fresh task
      }
    } catch (Exception e) {
      // fall through
    }

    kafkaService.sendTask(message, uuid);
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
              false);
      sendMessage(projectId, objectMapper.writeValueAsString(event));
    } catch (Exception e) {
      log.severe("Failed to send WS error event: " + e.getMessage());
    }
  }
}
