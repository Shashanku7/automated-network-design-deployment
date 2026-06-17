package org.acme.gateway.models;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.UUID;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record WorkflowState(
    UUID projectId,
    String status,
    int currentPhase,
    List<PhaseResult> completedPhases
) {}
