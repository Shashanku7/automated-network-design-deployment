package org.acme.gateway.models;

import module java.base;

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
    CHUNK,
    TOOL_CALL,
    TOOL_RESULT,
    RESULT
  }
}
