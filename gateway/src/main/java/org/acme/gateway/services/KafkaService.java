package org.acme.gateway.services;

import module java.base;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.UUID;
import org.acme.gateway.APIWebSocket;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.models.WebSocketMessage;
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.eclipse.microprofile.reactive.messaging.Emitter;
import org.eclipse.microprofile.reactive.messaging.Incoming;

@ApplicationScoped
public class KafkaService {
  @Inject
  @Channel("agent-tasks")
  Emitter<AgentTask> taskEmitter;

  @Inject APIWebSocket webSocket;
  @Inject ObjectMapper objectMapper;

  public void sendTask(String message, UUID projectId) {
    try {
      WebSocketMessage wsMsg = objectMapper.readValue(message, WebSocketMessage.class);
      AgentTask task =
          new AgentTask(
              projectId,
              wsMsg.taskId() != null ? wsMsg.taskId() : UUID.randomUUID(),
              0, // Initial phase or derive from wsMsg
              wsMsg.agentName(),
              wsMsg.content(),
              null // history
              );
      taskEmitter.send(task);
    } catch (Exception e) {
      // Log error or send error back via WS
    }
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    try {
      String json = objectMapper.writeValueAsString(event);
      webSocket.sendMessage(event.projectId(), json);
    } catch (Exception e) {
      // Log error
    }
  }
}
