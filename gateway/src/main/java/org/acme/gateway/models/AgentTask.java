package org.acme.gateway.models;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.UUID;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AgentTask(
    UUID projectId,
    UUID taskId,
    int phase,
    String agentTarget,
    String inputContext,
    List<ChatMessage> history) {
  public AgentTask() {
    this(null, null, 0, null, null, null);
  }

  @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
  public record ChatMessage(Role role, String content) {
    public enum Role {
      user,
      assistant,
      system
    }
  }
}
