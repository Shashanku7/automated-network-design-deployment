package org.acme.gateway.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.models.PipelineState;
import org.acme.gateway.repositories.AgentTaskRepository;

@ApplicationScoped
public class PipelineManager {
  private final Map<UUID, PipelineState> states = new ConcurrentHashMap<>();

  @Inject
  AgentTaskRepository agentTaskRepository;

  public PipelineState getOrCreateState(UUID projectId) {
    return states.computeIfAbsent(projectId, PipelineState::new);
  }

  public AgentTask createNextTask(UUID projectId) {
    PipelineState state = getOrCreateState(projectId);
    return new AgentTask(
        projectId,
        UUID.randomUUID(),
        state.getCurrentPhase(),
        getAgentTarget(state.getCurrentPhase()),
        state.buildInputContext(),
        state.getHistory());
  }

  public void storePhaseOutput(UUID projectId, String output) {
    PipelineState state = getOrCreateState(projectId);
    state.setLastOutput(output);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.ASSISTANT, output));
    switch (state.getCurrentPhase()) {
      case 1 -> state.setRephrasedPrompt(output);
      case 2 -> state.setTopologyDesign(output);
      case 3 -> state.setBillOfMaterials(output);
      case 4 -> state.setD2Diagram(output);
    }
  }

  public AgentTask advancePhase(UUID projectId) {
    PipelineState state = getOrCreateState(projectId);
    if (state.getCurrentPhase() <= 5) {
      state.setCurrentPhase(state.getCurrentPhase() + 1);
    }
    int nextPhase = state.getCurrentPhase();
    if (nextPhase > 5) {
      return null;
    }
    return createNextTask(projectId);
  }

  public AgentTask advanceAfterPhaseComplete(UUID projectId, String output) {
    storePhaseOutput(projectId, output);
    return advancePhase(projectId);
  }

  public void rehydrateFromDb(UUID projectId) {
    var completed = agentTaskRepository.findCompletedByProjectId(projectId);
    if (completed.isEmpty()) return;
    var state = getOrCreateState(projectId);
    for (var task : completed) {
      var out = task.getOutput() != null ? task.getOutput() : "";
      state.getHistory().add(
          new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.ASSISTANT, out));
      switch (task.getPhase()) {
        case 1 -> state.setRephrasedPrompt(out);
        case 2 -> state.setTopologyDesign(out);
        case 3 -> state.setBillOfMaterials(out);
        case 4 -> state.setD2Diagram(out);
      }
    }
    var last = completed.getLast();
    state.setCurrentPhase(last.getPhase() + 1);
    state.setLastOutput(last.getOutput() != null ? last.getOutput() : "");
  }

  private String getAgentTarget(int phase) {
    return switch (phase) {
      case 1 -> "prompt_rephraser";
      case 2 -> "topology_designer";
      case 3 -> "device_selector";
      case 4 -> "d2_diagram_generator";
      case 5 -> "cli_config_generator";
      default -> "unknown";
    };
  }
}
