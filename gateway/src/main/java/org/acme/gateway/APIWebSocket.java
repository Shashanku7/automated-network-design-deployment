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
        log.info("WS approval msg projectId=" + projectId + " approved=" + approved);
        if (approved) {
          kafkaService.emitNextTask(uuid);
        } else {
          String feedback = tree.has("feedback") ? tree.get("feedback").asText() : "";
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
      // Not JSON or no approved field — treat as regular prompt
    }

    // Handle resume — continue from current phase, no new user message
    try {
      var tree = objectMapper.readTree(message);
      if (tree.has("resume") && tree.get("resume").asBoolean()) {
        log.info("WS resume projectId=" + projectId);
        kafkaService.resumeWorkflow(uuid);
        return;
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
}
