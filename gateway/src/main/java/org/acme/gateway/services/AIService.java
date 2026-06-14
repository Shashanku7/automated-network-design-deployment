package org.acme.gateway.services;

import module java.base;

import jakarta.ws.rs.Path;

public interface AIService {
  @Path("rephrase")
  String getRephrasedPrompt(InputStream initial);

  @Path("topology")
  String getNetworkTopology(InputStream prompt);

  @Path("selector")
  String getDevices(InputStream prompt);

  @Path("diagram")
  byte[] getDiagram(InputStream prompt);

  @Path("cli-config")
  String getCliConfig(InputStream prompt);
}
