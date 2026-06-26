package org.acme.gateway.models;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

public class PipelineState {
  @Getter private final UUID projectId;
  @Getter @Setter private int currentPhase = 1;
  @Getter private final List<AgentTask.ChatMessage> history = new ArrayList<>();
  @Getter @Setter private String lastOutput = "";
  @Getter @Setter private String rephrasedPrompt = "";
  @Getter @Setter private String topologyDesign = "";
  @Getter @Setter private String billOfMaterials = "";
  @Getter @Setter private String d2Diagram = "";

  public PipelineState(UUID projectId) {
    this.projectId = projectId;
  }

  public String buildInputContext() {
    var ctx = switch (currentPhase) {
      case 1 -> lastOutput; // Initial user prompt
      case 2 -> rephrasedPrompt;
      case 3 ->
          "## Refined Requirements\n"
              + rephrasedPrompt
              + "\n\n## Approved Topology\n"
              + topologyDesign;
      case 4 ->
          "## Approved Topology\n"
              + topologyDesign
              + "\n\n## Bill of Materials\n"
              + billOfMaterials;
      case 5 ->
          "## Approved Topology\n"
              + topologyDesign
              + "\n\n## Bill of Materials\n"
              + billOfMaterials
              + "\n\n## D2 Diagram Code\n```d2\n"
              + d2Diagram
              + "\n```";
      default -> "";
    };
    if (currentPhase >= 2 && lastOutput != null && lastOutput.contains("## Revision Request\n")) {
      int revIdx = lastOutput.indexOf("## Revision Request\n");
      ctx = ctx + "\n\n" + lastOutput.substring(revIdx);
    }
    return ctx;
  }
}
