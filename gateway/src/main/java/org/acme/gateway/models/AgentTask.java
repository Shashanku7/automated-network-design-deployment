package org.acme.gateway.models;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonInclude;
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
    List<ChatMessage> history,
    @JsonInclude(JsonInclude.Include.NON_NULL) Boolean approved,
    @JsonInclude(JsonInclude.Include.NON_NULL) String feedback) {
  public AgentTask() {
    this(null, null, 0, null, null, null, null, null);
  }

  public AgentTask(UUID projectId, UUID taskId, int phase, String agentTarget, String inputContext, List<ChatMessage> history) {
    this(projectId, taskId, phase, agentTarget, inputContext, history, null, null);
  }

  @JsonInclude(JsonInclude.Include.NON_NULL)
  @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
  public record ChatMessage(Role role, String content, String timestamp) {
    public ChatMessage(Role role, String content) {
      this(role, content, null);
    }

    public enum Role {
      USER,
      ASSISTANT,
      SYSTEM;

      @JsonCreator
      public static Role fromString(String value) {
        return value == null ? null : Role.valueOf(value.toUpperCase());
      }
    }
  }
}
