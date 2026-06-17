package org.acme.gateway.models;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record PhaseResult(
    int phase,
    String agentTarget,
    String output,
    String status
) {}
