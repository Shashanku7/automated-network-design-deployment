package org.acme.gateway.models;

import java.util.List;
import java.util.UUID;

public record AgentTask(
    UUID projectId,
    UUID taskId,
    int phase,
    String agentTarget,
    String inputContext,
    List<HistoryEntry> history) {
  public AgentTask() {
    this(null, null, 0, null, null, null);
  }

  public record HistoryEntry(String role, String content) {}
}
