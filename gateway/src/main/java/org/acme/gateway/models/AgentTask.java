package org.acme.gateway.models;

import module java.base;

public record AgentTask(
    UUID projectId, UUID taskId, int phase, String agentTarget, String inputContext) {}
