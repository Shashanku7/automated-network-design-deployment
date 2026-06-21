package org.acme.gateway.models;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.OffsetDateTime;
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
    boolean isFinal,
    OffsetDateTime timestamp) {

  @JsonCreator(mode = JsonCreator.Mode.PROPERTIES)
  public static AgentEvent create(
      @JsonProperty("project_id") UUID projectId,
      @JsonProperty("task_id") UUID taskId,
      @JsonProperty("agent_name") String agentName,
      @JsonProperty("event_type") EventType eventType,
      @JsonProperty("data") String data,
      @JsonProperty("payload") Map<String, Object> payload,
      @JsonProperty("is_final") boolean isFinal,
      @JsonProperty("timestamp") OffsetDateTime timestamp) {
    return new AgentEvent(projectId, taskId, agentName, eventType, data, payload, isFinal,
        timestamp != null ? timestamp : OffsetDateTime.now());
  }

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
