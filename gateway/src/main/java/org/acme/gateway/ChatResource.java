package org.acme.gateway;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import org.acme.gateway.models.ChatRequest;
import org.acme.gateway.models.ChatResponse;
import org.acme.gateway.services.AiServiceClient;
import org.eclipse.microprofile.rest.client.inject.RestClient;

@Path("/api/chat")
public class ChatResource {

    @Inject
    @RestClient
    AiServiceClient aiServiceClient;

    @POST
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public ChatResponse chat(ChatRequest request) {
        return aiServiceClient.chat(request);
    }
}
