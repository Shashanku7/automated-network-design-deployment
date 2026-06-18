package org.acme.gateway.models;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.Map;
import java.util.UUID;

@JsonInclude
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AgentEvent(
    UUID projectId,
    UUID taskId,
    String agentName,
    EventType eventType,
    String data,
    Map<String, Object> payload,
    boolean isFinal) {

  public enum EventType {
    TOKEN,
    TOOL_CALL,
    TOOL_RESULT,
    FINAL_ANSWER,
    PHASE_APPROVED,
    APPROVAL_REQUIRED,
    DIAGRAM_READY,
    DIAGRAM_ERROR,
    ERROR;

    @JsonCreator
    public static EventType fromString(String value) {
      return EventType.valueOf(value.toUpperCase());
    }
  }
}
