package org.acme.gateway.models;

import module java.base;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude
public record AgentEvent(UUID projectId, UUID taskId, String agentName, EventType event) {

  public enum EventType {
    TOKEN,
    TOOL_CALL,
    TOOL_RESULT,
    FINAL_ANSWER,
    ERROR;
  }
}
