package org.acme.gateway;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import java.util.UUID;
import org.acme.gateway.services.KafkaService;

@Path("/api/tasks")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class APIResource {

  @Inject KafkaService kafkaService;

  @POST
  public Response createTask(CreateTaskRequest request) {
    kafkaService.sendTask(request.message(), UUID.fromString(request.projectId()));

    return Response.accepted().build();
  }

  public record CreateTaskRequest(String projectId, String message) {}
}
