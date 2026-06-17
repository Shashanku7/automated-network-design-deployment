package org.acme.gateway.services;

import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import java.util.List;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

@Path("/")
@RegisterRestClient
public interface AIService {

  record ChatHistoryItem(String role, String content) {}

  record ChatRequest(String message, List<ChatHistoryItem> history) {}

  record ChatResponse(String role, String content, String timestamp) {}

  @POST
  @Path("api/chat")
  ChatResponse sendChat(ChatRequest request);

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
