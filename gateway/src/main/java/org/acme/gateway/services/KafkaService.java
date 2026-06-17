package org.acme.gateway.services;

import module java.base;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import java.util.UUID;
import lombok.extern.java.Log;
import org.acme.gateway.APIWebSocket;
import org.acme.gateway.entities.AgentTaskEntity;
import org.acme.gateway.entities.ConversationEntity;
import org.acme.gateway.entities.MessageEntity;
import org.acme.gateway.models.AgentEvent;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.repositories.AgentTaskRepository;
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
  @Inject AgentTaskRepository agentTaskRepository;

  @Transactional
  public void sendTask(String message, UUID projectId) {
    var state = pipelineManager.getOrCreateState(projectId);
    state.setLastOutput(message);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.USER, message));
    var task = pipelineManager.createNextTask(projectId);
    log.info("Log Task:" + task.toString());
    taskEmitter.send(task);

    try {
      var convId = ensureConversation(projectId);
      var content = extractContent(message);
      var seq = messageRepository.countByConversationId(convId) + 1;
      messageRepository.persist(new MessageEntity(convId, seq, "user", content));
      agentTaskRepository.persist(new AgentTaskEntity(task.taskId(), convId, projectId, task.phase(), task.agentTarget(), task.inputContext()));
    } catch (Exception e) {
      log.severe("Failed to persist user message: " + e.getMessage());
    }
  }

  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    if (event.isFinal() && event.eventType() == AgentEvent.EventType.FINAL_ANSWER) {
      pipelineManager.updateStateAfterPhase(event.projectId(), event.data());

      try {
        var convId = ensureConversation(event.projectId());
        if (event.data() != null) {
          var seq = messageRepository.countByConversationId(convId) + 1;
          messageRepository.persist(new MessageEntity(convId, seq, "assistant", event.data()));
        }

        // Mark task as completed
        agentTaskRepository.findByIdOptional(event.taskId()).ifPresent(t -> {
          t.setStatus("completed");
          t.setCompletedAt(java.time.OffsetDateTime.now());
        });
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

  private UUID ensureConversation(UUID projectId) {
    var existing = conversationRepository.find("projectId", projectId).firstResult();
    if (existing != null) {
      return existing.getId();
    }
    var conv = new ConversationEntity(projectId, "Design Workflow");
    conversationRepository.persistAndFlush(conv);
    return conv.getId();
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
