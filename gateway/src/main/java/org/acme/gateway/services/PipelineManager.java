package org.acme.gateway.services;

import jakarta.enterprise.context.ApplicationScoped;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.acme.gateway.models.AgentTask;
import org.acme.gateway.models.PipelineState;

@ApplicationScoped
public class PipelineManager {
  private final Map<UUID, PipelineState> states = new ConcurrentHashMap<>();

  public PipelineState getOrCreateState(UUID projectId) {
    return states.computeIfAbsent(projectId, PipelineState::new);
  }

  public AgentTask createNextTask(UUID projectId) {
    PipelineState state = getOrCreateState(projectId);
    UUID taskId = UUID.randomUUID();
    if (state.getOriginalTaskId() == null) {
      state.setOriginalTaskId(taskId);
    }
    return new AgentTask(
        projectId,
        taskId,
        state.getCurrentPhase(),
        getAgentTarget(state.getCurrentPhase()),
        state.buildInputContext(),
        state.getHistory());
  }

  public UUID getOriginalTaskId(UUID projectId) {
    PipelineState state = states.get(projectId);
    return state != null ? state.getOriginalTaskId() : null;
  }

  public void updateStateAfterPhase(UUID projectId, String output) {
    PipelineState state = getOrCreateState(projectId);
    int phase = state.getCurrentPhase();
    state.setLastOutput(output);
    state.getHistory().add(new AgentTask.ChatMessage(AgentTask.ChatMessage.Role.ASSISTANT, output));

    switch (phase) {
      case 1 -> state.setRephrasedPrompt(output);
      case 2 -> state.setTopologyDesign(output);
      case 3 -> state.setBillOfMaterials(output);
      case 4 -> state.setD2Diagram(output);
      case 5 -> state.setReactCode(output);
      case 6 -> state.setCliConfig(output);
    }
    if (phase < 6) state.setCurrentPhase(phase + 1);
  }

  private String getAgentTarget(int phase) {
    return switch (phase) {
      case 1 -> "prompt_rephraser";
      case 2 -> "topology_designer";
      case 3 -> "device_selector";
      case 4 -> "d2_diagram_generator";
      case 5 -> "react_topology_architect";
      case 6 -> "cli_config_generator";
      default -> "unknown";
    };
  }
}
