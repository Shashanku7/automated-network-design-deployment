package org.acme.gateway.models;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;
import java.util.UUID;

@JsonInclude
public record AgentEvent(
    UUID projectId,
    UUID taskId,
    String agentName,
    @JsonProperty("event_type") EventType eventType,
    String data,
    Map<String, Object> payload,
    @JsonProperty("is_final") Boolean isFinal) {

  public enum EventType {
    @JsonProperty("token")
    TOKEN,
    @JsonProperty("tool_call")
    TOOL_CALL,
    @JsonProperty("tool_result")
    TOOL_RESULT,
    @JsonProperty("final_answer")
    FINAL_ANSWER,
    @JsonProperty("error")
    ERROR;
  }
}
