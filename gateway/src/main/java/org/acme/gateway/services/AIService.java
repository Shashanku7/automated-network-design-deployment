package org.acme.gateway.services;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import java.util.List;
import java.util.Map;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

@Path("/")
@RegisterRestClient
public interface AIService {

  record ChatHistoryItem(String role, String content) {}

  record ChatRequest(String message, List<ChatHistoryItem> history, @JsonProperty("project_id") String projectId, @JsonProperty("screen_context") String screenContext) {}

  record ChatResponse(String role, String content, String timestamp) {}

  record PersistentChatHistoryResponse(
      @JsonProperty("project_id") String projectId,
      @JsonProperty("conversation_id") String conversationId,
      @JsonProperty("conversation_key") String conversationKey,
      @JsonProperty("conversation_messages") List<Map<String, Object>> conversationMessages,
      @JsonProperty("phase_messages") Map<String, List<Map<String, Object>>> phaseMessages,
      @JsonProperty("merged_messages") List<Map<String, Object>> mergedMessages) {}

  @POST
  @Path("api/chat")
  ChatResponse sendChat(ChatRequest request);

  @GET
  @Path("api/chat-history/{projectId}")
  PersistentChatHistoryResponse getChatHistory(
      @PathParam("projectId") String projectId,
      @QueryParam("conversation_id") String conversationId);

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
