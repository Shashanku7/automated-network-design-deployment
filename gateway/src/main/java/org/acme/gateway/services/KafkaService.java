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
    log.info("sendTask START projectId=" + projectId + " msgPreview=" + message.substring(0, Math.min(100, message.length())));
    var state = pipelineManager.getOrCreateState(projectId);
    log.info("sendTask state phase=" + state.getCurrentPhase() + " lastOutput=" + (state.getLastOutput() == null ? "null" : "notNull"));

    state.setLastOutput(message);
    log.info("sendTask after setLastOutput lastOutput=" + (state.getLastOutput() == null ? "null" : "notNull"));

    var chatMsg = new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.USER, message);
    log.info("sendTask chatMsg content=" + (chatMsg.content() == null ? "null" : "notNull") + " role=" + chatMsg.role());
    state.getHistory().add(chatMsg);
    log.info("sendTask history size=" + state.getHistory().size());

    var task = pipelineManager.createNextTask(projectId);
    log.info("sendTask taskId=" + task.taskId() + " phase=" + task.phase() + " agent=" + task.agentTarget());
    log.info("sendTask inputContext=" + (task.inputContext() == null ? "null" : "notNull"));
    log.info("sendTask history.size=" + task.history().size());
    if (!task.history().isEmpty()) {
      for (int i = 0; i < task.history().size(); i++) {
        var h = task.history().get(i);
        log.info("sendTask history[" + i + "] role=" + h.role() + " content=" + (h.content() == null ? "null" : "notNull(" + h.content().length() + "chars)"));
      }
    }
    log.info("sendTask JSON=" + task.toString());
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
    log.info("consumeEvent projectId=" + event.projectId() + " taskId=" + event.taskId() + " type=" + event.eventType() + " isFinal=" + event.isFinal());
    log.info("consumeEvent agent=" + event.agentName() + " dataLen=" + (event.data() == null ? 0 : event.data().length()));

    if (event.isFinal() && event.eventType() == AgentEvent.EventType.FINAL_ANSWER) {
      log.info("consumeEvent FINAL_ANSWER data=" + (event.data() == null ? "null" : event.data().substring(0, Math.min(200, event.data().length()))));
      pipelineManager.updateStateAfterPhase(event.projectId(), event.data());

      try {
        var convId = ensureConversation(event.projectId());
        if (event.data() != null) {
          var seq = messageRepository.countByConversationId(convId) + 1;
          log.info("consumeEvent persist msg convId=" + convId + " seq=" + seq + " role=assistant");
          messageRepository.persist(new MessageEntity(convId, seq, "assistant", event.data()));
        }

        agentTaskRepository.findByIdOptional(event.taskId()).ifPresent(t -> {
          log.info("consumeEvent mark task complete taskId=" + event.taskId());
          t.setStatus("completed");
          t.setCompletedAt(java.time.OffsetDateTime.now());
        });
      } catch (Exception e) {
        log.severe("Failed to persist agent response: " + e.getMessage());
      }
    }

    try {
      String json = objectMapper.writeValueAsString(event);
      log.info("consumeEvent forward to WS projectId=" + event.projectId() + " jsonLen=" + json.length());
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
