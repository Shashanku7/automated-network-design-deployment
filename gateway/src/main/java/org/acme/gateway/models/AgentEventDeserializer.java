package org.acme.gateway.models;

import io.quarkus.kafka.client.serialization.ObjectMapperDeserializer;

public class AgentEventDeserializer extends ObjectMapperDeserializer<AgentEvent> {

  public AgentEventDeserializer() {
    super(AgentEvent.class);
  }
}
