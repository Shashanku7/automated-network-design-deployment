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

  @Inject APIWebSocket webSocket;

  public void sendTask(String message, UUID projectId) {
    // Logic to convert WSMessage -> AgentTask
    // AgentTask task = new AgentTask(projectId, message);
    var task = new AgentTask();
    taskEmitter.send(task);
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    // Forward event to the correct WebSocket session
    webSocket.sendMessage(event.projectId(), event.toString());
  }
}
