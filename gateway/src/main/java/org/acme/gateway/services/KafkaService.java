package org.acme.gateway.services;

import module java.base;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.acme.gateway.APIWebSocket;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.models.AgentTask;
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.eclipse.microprofile.reactive.messaging.Emitter;
import org.eclipse.microprofile.reactive.messaging.Incoming;

@ApplicationScoped
public class KafkaService {
  @Inject
  @Channel("agent-tasks")
  Emitter<AgentTask> taskEmitter;

  @Inject PipelineManager pipelineManager;
  @Inject APIWebSocket webSocket;

  public void sendTask(String message, UUID projectId) {
    var state = pipelineManager.getOrCreateState(projectId);
    state.setLastOutput(message);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.user, message));

    var task = pipelineManager.createNextTask(projectId);
    taskEmitter.send(task);
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    if (event.isFinal() && event.eventType() == AgentEvent.EventType.FINAL_ANSWER) {
      pipelineManager.updateStateAfterPhase(event.projectId(), event.data());
    }
    // Forward event as JSON to UI
    webSocket.sendMessage(event.projectId(), event.toString());
  }
}
