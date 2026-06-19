package org.acme.gateway.services;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
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
  private final Map<UUID, PendingApproval> pendingApprovals = new ConcurrentHashMap<>();

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
    emitTask("sendTask", task);

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

  @Transactional
  @Incoming("agent-events")
  public void consumeEvent(AgentEvent event) {
    log.info("consumeEvent projectId=" + event.projectId() + " taskId=" + event.taskId() + " type=" + event.eventType() + " isFinal=" + event.isFinal());
    log.info("consumeEvent agent=" + event.agentName() + " dataLen=" + (event.data() == null ? 0 : event.data().length()));

    if (event.isFinal() && event.eventType() == AgentEvent.EventType.FINAL_ANSWER) {
      var existingTask = agentTaskRepository.findByIdOptional(event.taskId());
      if (existingTask.isPresent() && "completed".equalsIgnoreCase(existingTask.get().getStatus())) {
        log.info("consumeEvent duplicate FINAL_ANSWER ignored taskId=" + event.taskId());
        return;
      }
      log.info("consumeEvent FINAL_ANSWER data=" + (event.data() == null ? "null" : event.data().substring(0, Math.min(200, event.data().length()))));

      // Persist agent response & mark task complete
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
          t.setOutput(event.data());
          t.setCompletedAt(java.time.OffsetDateTime.now());
        });
      } catch (Exception e) {
        log.severe("Failed to persist agent response: " + e.getMessage());
      }

      // Store output but DON'T auto-advance — wait for HITL approval
      pipelineManager.storePhaseOutput(event.projectId(), event.data());
      int phase = pipelineManager.getOrCreateState(event.projectId()).getCurrentPhase();
      pendingApprovals.put(event.projectId(), new PendingApproval(event.taskId(), phase, event.agentName()));

      // Send APPROVAL_REQUIRED event to frontend
      try {
        var approvalEvent = new AgentEvent(
            event.projectId(), event.taskId(), event.agentName(),
            AgentEvent.EventType.APPROVAL_REQUIRED,
            "Phase completed, awaiting approval",
            Map.of(
                "task_id", event.taskId().toString(),
                "phase", phase,
                "agent_name", event.agentName()),
            false);
        var approvalJson = objectMapper.writeValueAsString(approvalEvent);
        webSocket.sendMessage(event.projectId().toString(), approvalJson);
      } catch (Exception e) {
        log.severe("Failed to send APPROVAL_REQUIRED event: " + e.getMessage());
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

  @Transactional
  public void emitNextTask(UUID projectId) {
    var nextTask = pipelineManager.advancePhase(projectId);
    if (nextTask != null) {
      log.info("emitNextTask projectId=" + projectId + " phase=" + nextTask.phase() + " agent=" + nextTask.agentTarget());
      try {
        var convId = ensureConversation(projectId);
        agentTaskRepository.persist(new AgentTaskEntity(nextTask.taskId(), convId, projectId, nextTask.phase(), nextTask.agentTarget(), nextTask.inputContext()));
      } catch (Exception e) {
        log.severe("emitNextTask persist error: " + e.getMessage());
      }
      emitTask("emitNextTask", nextTask);

      // Notify frontend phase was approved
      try {
        var approvedEvent = new AgentEvent(projectId, nextTask.taskId(), nextTask.agentTarget(),
            AgentEvent.EventType.PHASE_APPROVED,
            nextTask != null ? "Phase approved, proceeding to next phase" : "Workflow complete",
            null, nextTask == null);
        var approvedJson = objectMapper.writeValueAsString(approvedEvent);
        webSocket.sendMessage(projectId.toString(), approvedJson);
      } catch (Exception e) {
        log.severe("emitNextTask send PHASE_APPROVED error: " + e.getMessage());
      }
    } else {
      log.info("emitNextTask projectId=" + projectId + " workflow complete");
      try {
        var doneEvent = new AgentEvent(projectId, UUID.randomUUID(), "",
            AgentEvent.EventType.PHASE_APPROVED,
            "Workflow complete", null, true);
        webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(doneEvent));
      } catch (Exception e) {
        log.severe("emitNextTask send complete error: " + e.getMessage());
      }
    }
  }

  public Optional<PendingApproval> getPendingApproval(UUID projectId) {
    return Optional.ofNullable(pendingApprovals.get(projectId));
  }

  public boolean clearPendingApproval(UUID projectId, UUID taskId, Integer phase) {
    final boolean[] cleared = {false};
    pendingApprovals.compute(
        projectId,
        (id, current) -> {
          if (current == null) return null;
          if (!current.taskId().equals(taskId)) return current;
          if (phase != null && phase > 0 && current.phase() != phase) return current;
          cleared[0] = true;
          return null;
        });
    return cleared[0];
  }

  public void replayPendingApproval(UUID projectId) {
    var pending = pendingApprovals.get(projectId);
    if (pending == null) return;
    try {
      var approvalEvent =
          new AgentEvent(
              projectId,
              pending.taskId(),
              pending.agentName(),
              AgentEvent.EventType.APPROVAL_REQUIRED,
              "Phase completed, awaiting approval",
              Map.of(
                  "task_id", pending.taskId().toString(),
                  "phase", pending.phase(),
                  "agent_name", pending.agentName()),
              false);
      webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(approvalEvent));
    } catch (Exception e) {
      log.severe("replayPendingApproval failed projectId=" + projectId + " error=" + e.getMessage());
    }
  }

  @Transactional
  public void resumeWorkflow(UUID projectId) {
    log.info("resumeWorkflow projectId=" + projectId);
    var state = pipelineManager.getOrCreateState(projectId);
    int phase = state.getCurrentPhase();
    log.info("resumeWorkflow state phase=" + phase);

    // If all 5 phases already done, send workflow complete
    if (phase > 5) {
      log.info("resumeWorkflow workflow already complete");
      try {
        var doneEvent = new AgentEvent(projectId, UUID.randomUUID(), "",
            AgentEvent.EventType.PHASE_APPROVED,
            "Workflow complete", null, true);
        webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(doneEvent));
      } catch (Exception e) {
        log.severe("resumeWorkflow send complete error: " + e.getMessage());
      }
      return;
    }

    var task = pipelineManager.createNextTask(projectId);
    log.info("resumeWorkflow taskId=" + task.taskId() + " phase=" + task.phase() + " agent=" + task.agentTarget());

    try {
      var convId = ensureConversation(projectId);
      agentTaskRepository.persist(new AgentTaskEntity(task.taskId(), convId, projectId, task.phase(), task.agentTarget(), task.inputContext()));
    } catch (Exception e) {
      log.severe("resumeWorkflow persist error: " + e.getMessage());
    }
    emitTask("resumeWorkflow", task);
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

  private void emitTask(String source, AgentTask task) {
    try {
      taskEmitter.send(task).whenComplete((ignored, error) -> {
        if (error != null) {
          log.severe(
              source
                  + " kafka send failed projectId="
                  + task.projectId()
                  + " taskId="
                  + task.taskId()
                  + " phase="
                  + task.phase()
                  + " error="
                  + error.getMessage());
          return;
        }
        log.info(
            source
                + " kafka send success projectId="
                + task.projectId()
                + " taskId="
                + task.taskId()
                + " phase="
                + task.phase());
      });
    } catch (Exception e) {
      log.severe(
          source
              + " kafka send invocation failed projectId="
              + task.projectId()
              + " taskId="
              + task.taskId()
              + " phase="
              + task.phase()
              + " error="
              + e.getMessage());
    }
  }

  public record PendingApproval(UUID taskId, int phase, String agentName) {}
}
