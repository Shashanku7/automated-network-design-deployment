package org.acme.gateway.services;

import module java.base;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import lombok.extern.java.Log;
import org.acme.gateway.APIWebSocket;
import org.acme.gateway.entities.ConversationEntity;
import org.acme.gateway.entities.MessageEntity;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.repositories.ConversationRepository;
import org.acme.gateway.repositories.MessageRepository;
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
  @Inject ConversationRepository conversationRepository;
  @Inject MessageRepository messageRepository;

  // Tracks active conversation per project (projectId -> conversationId)
  private final Map<UUID, UUID> projectConversations = new ConcurrentHashMap<>();

  @Transactional
  public void sendTask(String message, UUID projectId) {
    var state = pipelineManager.getOrCreateState(projectId);
    state.setLastOutput(message);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.USER, message));
    var task = pipelineManager.createNextTask(projectId);
    log.info("Log Task:" + task.toString());
    taskEmitter.send(task);

    // Persist user message to DB
    try {
      ensureConversation(projectId);
      var convId = projectConversations.get(projectId);
      var content = extractContent(message);
      var seq = messageRepository.countByConversationId(convId) + 1;
      var msg = new MessageEntity(convId, seq, "user", content);
      messageRepository.persist(msg);
    } catch (Exception e) {
      log.severe("Failed to persist user message: " + e.getMessage());
    }
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    if (event.isFinal() && event.eventType() == AgentEvent.EventType.FINAL_ANSWER) {
      pipelineManager.updateStateAfterPhase(event.projectId(), event.data());

      // Persist assistant response to DB
      try {
        var convId = projectConversations.get(event.projectId());
        if (convId != null && event.data() != null) {
          var seq = messageRepository.countByConversationId(convId) + 1;
          var msg = new MessageEntity(convId, seq, "assistant", event.data());
          messageRepository.persist(msg);
        }
      } catch (Exception e) {
        log.severe("Failed to persist agent response: " + e.getMessage());
      }
    }

    try {
      String json = objectMapper.writeValueAsString(event);
      webSocket.sendMessage(event.projectId().toString(), json);
    } catch (Exception e) {
      log.severe("Failed to serialize AgentEvent: " + e.getMessage());
    }
  }

  private void ensureConversation(UUID projectId) {
    if (!projectConversations.containsKey(projectId)) {
      var conv = new ConversationEntity(projectId, "Design Workflow");
      conversationRepository.persist(conv);
      projectConversations.put(projectId, conv.getId());
    }
  }

  private String extractContent(String messageJson) {
    try {
      var tree = objectMapper.readTree(messageJson);
      var content = tree.get("content");
      return content != null ? content.asText() : messageJson;
    } catch (Exception e) {
      return messageJson;
    }
  }
}
