package org.acme.gateway.services;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;
import java.util.UUID;
import lombok.extern.java.Log;
import org.acme.gateway.APIWebSocket;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.models.AgentTask;
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.eclipse.microprofile.reactive.messaging.Emitter;
import org.eclipse.microprofile.reactive.messaging.Incoming;

@ApplicationScoped
@Log
public class KafkaService {
  @Inject
  @Channel("agent-tasks")
  Emitter<AgentTask> taskEmitter;

  @Inject PipelineManager pipelineManager;
  @Inject APIWebSocket webSocket;
  @Inject ObjectMapper objectMapper;

  public void sendTask(String message, UUID projectId) {
    try {
      var json = objectMapper.readTree(message);
      if (json.has("approved")) {
        Boolean approved = json.get("approved").asBoolean();
        String feedback = json.has("feedback") ? json.get("feedback").asText() : null;
        UUID originalTaskId = pipelineManager.getOriginalTaskId(projectId);
        if (originalTaskId == null) {
          originalTaskId = UUID.randomUUID();
        }
        var task = new AgentTask(
            projectId,
            originalTaskId,
            -1,
            "feedback",
            message,
            List.of(),
            approved,
            feedback);
        log.info("Feedback task for " + projectId + " taskId=" + originalTaskId + " approved=" + approved);
        taskEmitter.send(task);
        return;
      }
    } catch (Exception e) {
      log.warning("sendTask parse error: " + e.getMessage());
    }

    var state = pipelineManager.getOrCreateState(projectId);
    state.setLastOutput(message);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.USER, message));
    var task = pipelineManager.createNextTask(projectId);
    log.info("Task:" + task.toString());
    taskEmitter.send(task);
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    if (event.isFinal() && "FINAL_ANSWER".equals(event.eventType())) {
      pipelineManager.updateStateAfterPhase(event.projectId(), event.data());
    }
    try {
      String json = objectMapper.writeValueAsString(event);
      webSocket.sendMessage(event.projectId().toString(), json);
    } catch (Exception e) {
      log.severe("Failed to serialize AgentEvent: " + e.getMessage());
    }
  }
}
