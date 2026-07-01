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
import org.acme.gateway.repositories.ProjectRepository;

@ApplicationScoped
@Log
public class WorkflowOrchestrator {
  @Inject PipelineManager pipelineManager;
  @Inject APIWebSocket webSocket;
  @Inject ObjectMapper objectMapper;
  @Inject ProjectRepository projectRepository;
  @Inject AgentTaskRepository agentTaskRepository;
  @Inject ConversationRepository conversationRepository;
  @Inject MessageRepository messageRepository;
  @Inject KafkaService kafkaService;

  private final Map<UUID, PendingApproval> pendingApprovals = new ConcurrentHashMap<>();

  public void handlePhaseComplete(UUID projectId, UUID taskId, String agentName, int phase, String output) {
    log.info("handlePhaseComplete projectId=" + projectId + " phase=" + phase);
    pipelineManager.storePhaseOutput(projectId, output);
    if (phase >= 5) {
      completeWorkflow(projectId);
    } else {
      requestApproval(projectId, taskId, phase, agentName);
    }
  }

  private void requestApproval(UUID projectId, UUID taskId, int phase, String agentName) {
    pendingApprovals.put(projectId, new PendingApproval(taskId, phase, agentName));
    try {
      var approvalEvent = new AgentEvent(
          projectId, taskId, agentName,
          AgentEvent.EventType.APPROVAL_REQUIRED,
          "Phase completed, awaiting approval",
          Map.of(
              "task_id", taskId.toString(),
              "phase", phase,
              "agent_name", agentName),
          false,
          java.time.OffsetDateTime.now());
      var approvalJson = objectMapper.writeValueAsString(approvalEvent);
      webSocket.sendMessage(projectId.toString(), approvalJson);
    } catch (Exception e) {
      log.severe("Failed to send APPROVAL_REQUIRED event: " + e.getMessage());
    }
  }

  private void completeWorkflow(UUID projectId) {
    log.info("completeWorkflow projectId=" + projectId);
    projectRepository.findByIdOptional(projectId).ifPresent(p -> {
      p.setWorkflowStatus("complete");
    });
    try {
      var doneTaskId = UUID.randomUUID();
      var doneEvent = new AgentEvent(projectId, doneTaskId, "",
          AgentEvent.EventType.PHASE_APPROVED,
          "Workflow complete", Map.of("task_id", doneTaskId.toString(), "phase", 5), true,
          java.time.OffsetDateTime.now());
      webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(doneEvent));
    } catch (Exception e) {
      log.severe("completeWorkflow send error: " + e.getMessage());
    }
  }

  @Transactional
  public boolean handleApproval(UUID projectId, boolean approved, String feedback, UUID taskId, Integer phase) {
    log.info("handleApproval projectId=" + projectId + " approved=" + approved);
    var pending = getPendingApproval(projectId);
    if (pending.isEmpty()) {
      log.warning("handleApproval no pending approval for projectId=" + projectId);
      return false;
    }
    var expected = pending.get();
    if (taskId != null && !expected.taskId().equals(taskId)) {
      log.warning("handleApproval taskId mismatch expected=" + expected.taskId() + " got=" + taskId);
      return false;
    }
    if (phase != null && phase > 0 && expected.phase() != phase) {
      log.warning("handleApproval phase mismatch expected=" + expected.phase() + " got=" + phase);
      return false;
    }
    if (!approved && (feedback == null || feedback.trim().isEmpty())) {
      log.warning("handleApproval revision feedback empty");
      return false;
    }
    if (!approved && feedback.length() > 4000) {
      log.warning("handleApproval revision feedback too long length=" + feedback.length());
      return false;
    }
    if (!clearPendingApproval(projectId, taskId, phase)) {
      log.warning("handleApproval already processed");
      return false;
    }
    if (approved) {
      emitNextTask(projectId);
    } else {
      emitRevisionTask(projectId, feedback);
    }
    return true;
  }

  @Transactional
  public void emitNextTask(UUID projectId) {
    log.info("emitNextTask projectId=" + projectId);
    var nextTask = pipelineManager.advancePhase(projectId);
    if (nextTask != null) {
      log.info("emitNextTask phase=" + nextTask.phase() + " agent=" + nextTask.agentTarget());
      try {
        var project = projectRepository.findById(projectId);
        var userId = project != null ? project.getUserId() : null;
        var convId = ensureConversation(projectId, userId);
        var taskEntity = new AgentTaskEntity(nextTask.taskId(), convId, projectId, nextTask.phase(), nextTask.agentTarget(), nextTask.inputContext());
        taskEntity.setUserId(userId);
        agentTaskRepository.persist(taskEntity);
      } catch (Exception e) {
        log.severe("emitNextTask persist error: " + e.getMessage());
      }
      kafkaService.emitTask("emitNextTask", nextTask);
      try {
        var approvedEvent = new AgentEvent(projectId, nextTask.taskId(), nextTask.agentTarget(),
            AgentEvent.EventType.PHASE_APPROVED,
            "Phase approved, proceeding to next phase",
            null, false, java.time.OffsetDateTime.now());
        webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(approvedEvent));
      } catch (Exception e) {
        log.severe("emitNextTask send PHASE_APPROVED error: " + e.getMessage());
      }
    } else {
      log.info("emitNextTask projectId=" + projectId + " workflow complete");
      try {
        var doneTaskId = UUID.randomUUID();
        var doneEvent = new AgentEvent(projectId, doneTaskId, "",
            AgentEvent.EventType.PHASE_APPROVED,
            "Workflow complete", Map.of("task_id", doneTaskId.toString(), "phase", 5), true,
            java.time.OffsetDateTime.now());
        webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(doneEvent));
      } catch (Exception e) {
        log.severe("emitNextTask send complete error: " + e.getMessage());
      }
    }
  }

  private void emitRevisionTask(UUID projectId, String feedback) {
    log.info("emitRevisionTask projectId=" + projectId);
    var state = pipelineManager.getOrCreateState(projectId);
    String lastOut = state.getLastOutput();
    String revisedInput = (lastOut != null ? lastOut : "") + "\n\n## Revision Request\n" + feedback;
    var project = projectRepository.findById(projectId);
    var userId = project != null ? project.getUserId() : null;
    kafkaService.sendTask(revisedInput, projectId, userId);
  }

  public Optional<PendingApproval> getPendingApproval(UUID projectId) {
    var inMemory = pendingApprovals.get(projectId);
    if (inMemory != null) {
      return Optional.of(inMemory);
    }
    return recoverPendingApprovalFromDb(projectId);
  }

  public boolean clearPendingApproval(UUID projectId, UUID taskId, Integer phase) {
    final boolean[] cleared = {false};
    pendingApprovals.compute(projectId, (id, current) -> {
      if (current == null) return null;
      if (taskId != null && !current.taskId().equals(taskId)) return current;
      if (phase != null && phase > 0 && current.phase() != phase) return current;
      cleared[0] = true;
      return null;
    });
    return cleared[0];
  }

  public void replayPendingApproval(UUID projectId) {
    var pending = getPendingApproval(projectId).orElse(null);
    if (pending == null) return;
    try {
      var approvalEvent = new AgentEvent(projectId, pending.taskId(), pending.agentName(),
          AgentEvent.EventType.APPROVAL_REQUIRED, "Phase completed, awaiting approval",
          Map.of("task_id", pending.taskId().toString(), "phase", pending.phase(), "agent_name", pending.agentName()),
          false, java.time.OffsetDateTime.now());
      webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(approvalEvent));
    } catch (Exception e) {
      log.severe("replayPendingApproval failed projectId=" + projectId + " error=" + e.getMessage());
    }
  }

  @Transactional
  public void restartWorkflow(UUID projectId) {
    log.info("restartWorkflow projectId=" + projectId);
    pipelineManager.clearState(projectId);
    agentTaskRepository.delete("projectId", projectId);
    pendingApprovals.remove(projectId);
    conversationRepository.find("projectId", projectId).firstResultOptional().ifPresent(conv -> {
      messageRepository.delete("conversationId", conv.getId());
      conversationRepository.delete(conv);
    });
  }

  @Transactional
  public void resumeWorkflow(UUID projectId) {
    log.info("resumeWorkflow projectId=" + projectId);
    var state = pipelineManager.getOrCreateState(projectId);
    int phase = state.getCurrentPhase();
    log.info("resumeWorkflow state phase=" + phase);

    if (phase > 5) {
      log.info("resumeWorkflow workflow already complete");
      try {
        var doneTaskId = UUID.randomUUID();
        var doneEvent = new AgentEvent(projectId, doneTaskId, "",
            AgentEvent.EventType.PHASE_APPROVED, "Workflow complete",
            Map.of("task_id", doneTaskId.toString(), "phase", 5), true,
            java.time.OffsetDateTime.now());
        webSocket.sendMessage(projectId.toString(), objectMapper.writeValueAsString(doneEvent));
      } catch (Exception e) {
        log.severe("resumeWorkflow send complete error: " + e.getMessage());
      }
      return;
    }

    var pending = getPendingApproval(projectId);
    if (pending.isPresent()) {
      log.info("resumeWorkflow phase " + pending.get().phase() + " awaiting approval — re-sending APPROVAL_REQUIRED");
      replayPendingApproval(projectId);
      return;
    }

    if (agentTaskRepository.existsByProjectIdAndPhase(projectId, phase)) {
      log.info("resumeWorkflow phase " + phase + " task already exists — waiting");
      return;
    }

    var task = pipelineManager.createNextTask(projectId);
    log.info("resumeWorkflow taskId=" + task.taskId() + " phase=" + task.phase() + " agent=" + task.agentTarget());

    try {
      var project = projectRepository.findById(projectId);
      var userId = project != null ? project.getUserId() : null;
      var convId = ensureConversation(projectId, userId);
      var taskEntity = new AgentTaskEntity(task.taskId(), convId, projectId, task.phase(), task.agentTarget(), task.inputContext());
      taskEntity.setUserId(userId);
      agentTaskRepository.persist(taskEntity);
    } catch (Exception e) {
      log.severe("resumeWorkflow persist error: " + e.getMessage());
    }
    kafkaService.emitTask("resumeWorkflow", task);
  }

  private Optional<PendingApproval> recoverPendingApprovalFromDb(UUID projectId) {
    var latestCompleted = agentTaskRepository.findLatestCompletedByProjectId(projectId);
    if (latestCompleted.isEmpty()) return Optional.empty();
    var task = latestCompleted.get();
    var project = projectRepository.findByIdOptional(projectId);
    if (project.isPresent() && "complete".equals(project.get().getWorkflowStatus())) {
      return Optional.empty();
    }
    if (task.getPhase() >= 5) return Optional.empty();
    if (agentTaskRepository.existsByProjectIdAndPhase(projectId, task.getPhase() + 1)) {
      return Optional.empty();
    }
    if (task.getOutput() == null || task.getOutput().isBlank()) return Optional.empty();
    var recovered = new PendingApproval(task.getTaskId(), task.getPhase(), task.getAgentTarget());
    pendingApprovals.put(projectId, recovered);
    return Optional.of(recovered);
  }

  private UUID ensureConversation(UUID projectId, String userId) {
    var existing = conversationRepository.find("projectId", projectId).firstResult();
    if (existing != null) return existing.getId();
    var conv = new ConversationEntity(projectId, "Design Workflow");
    conv.setUserId(userId);
    conversationRepository.persistAndFlush(conv);
    return conv.getId();
  }

  public record PendingApproval(UUID taskId, int phase, String agentName) {}
}
