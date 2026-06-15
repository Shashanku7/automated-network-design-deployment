package org.acme.gateway.services;

import module java.base;

import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

@Path("/")
@RegisterRestClient
public interface AIService {

  @POST
  @Path("rephrase")
  String getRephrasedPrompt(String initial);

  @POST
  @Path("topology")
  String getNetworkTopology(String prompt);

  @POST
  @Path("selector")
  String getDevices(String prompt);

  @POST
  @Path("diagram")
  @Produces("image/png")
  byte[] getDiagram(String prompt);

  @POST
  @Path("cli-config")
  String getCliConfig(String prompt);
}
