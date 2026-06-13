package org.acme.gateway.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record WebSocketMessage(
    MessageType type,
    UUID projectId,
    UUID taskId,
    String agentName,
    EventType eventType,
    String content,
    Boolean approved,
    String feedback,
    Map<String, Object> payload,
    OffsetDateTime timestamp) {

  public enum MessageType {
    USER_INPUT,
    AGENT_EVENT,
    APPROVAL_REQ,
    APPROVAL_RES,
    ERROR
  }

  public enum EventType {
    @JsonProperty("chunk")
    CHUNK,
    @JsonProperty("tool_call")
    TOOL_CALL,
    @JsonProperty("tool_result")
    TOOL_RESULT,
    @JsonProperty("result")
    RESULT
  }
}
