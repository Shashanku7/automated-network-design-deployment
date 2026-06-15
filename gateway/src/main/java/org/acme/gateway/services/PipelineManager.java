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
    return new AgentTask(
        projectId,
        UUID.randomUUID(),
        state.getCurrentPhase(),
        getAgentTarget(state.getCurrentPhase()),
        state.buildInputContext(),
        state.getHistory());
  }

  public void updateStateAfterPhase(UUID projectId, String output) {
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
