package org.acme.gateway.models;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class PipelineState {
  private final UUID projectId;
  private int currentPhase = 1;
  private final List<AgentTask.ChatMessage> history = new ArrayList<>();
  private String lastOutput = "";
  private String rephrasedPrompt = "";
  private String topologyDesign = "";
  private String billOfMaterials = "";
  private String d2Diagram = "";

  public PipelineState(UUID projectId) {
    this.projectId = projectId;
  }

  public UUID getProjectId() {
    return projectId;
  }

  public int getCurrentPhase() {
    return currentPhase;
  }

  public void setCurrentPhase(int phase) {
    this.currentPhase = phase;
  }

  public List<AgentTask.ChatMessage> getHistory() {
    return history;
  }

  public String getLastOutput() {
    return lastOutput;
  }

  public void setLastOutput(String output) {
    this.lastOutput = output;
  }

  public String getRephrasedPrompt() {
    return rephrasedPrompt;
  }

  public void setRephrasedPrompt(String rephrasedPrompt) {
    this.rephrasedPrompt = rephrasedPrompt;
  }

  public String getTopologyDesign() {
    return topologyDesign;
  }

  public void setTopologyDesign(String topologyDesign) {
    this.topologyDesign = topologyDesign;
  }

  public String getBillOfMaterials() {
    return billOfMaterials;
  }

  public void setBillOfMaterials(String billOfMaterials) {
    this.billOfMaterials = billOfMaterials;
  }

  public String getD2Diagram() {
    return d2Diagram;
  }

  public void setD2Diagram(String d2Diagram) {
    this.d2Diagram = d2Diagram;
  }

  public String buildInputContext() {
    return switch (currentPhase) {
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
  }
}
