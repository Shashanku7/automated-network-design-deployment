package org.acme.gateway;

import module java.base;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.websocket.OnClose;
import jakarta.websocket.OnError;
import jakarta.websocket.OnMessage;
import jakarta.websocket.OnOpen;
import jakarta.websocket.Session;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import org.acme.gateway.services.KafkaService;

@ServerEndpoint("/chat/{projectId}")
@ApplicationScoped
public class APIWebSocket {
  @Inject KafkaService kafkaService;
  Map<UUID, Session> sessions = new ConcurrentHashMap<>();

  @OnOpen
  public void onOpen(Session session, @PathParam("projectId") String projectId) {
    var uuid = UUID.fromString(projectId);
    sessions.putIfAbsent(uuid, session);
  }

  @OnClose
  public void onClose(Session session, @PathParam("projectId") String projectId) {
    var uuid = UUID.fromString(projectId);
    sessions.remove(uuid);
  }

  @OnError
  public void OnError(
      Session session, @PathParam("projectId") String projectId, Throwable throwable) {
    var uuid = UUID.fromString(projectId);
    sessions.remove(uuid);
  }

  @OnMessage
  public void onMessage(String message, @PathParam("projectId") String projectId) {
    // Basic implementation: user sends feedback/input to trigger next step
    var uuid = UUID.fromString(projectId);
    kafkaService.sendTask(message, uuid);
  }

  public void sendMessage(String projectId, String content) {
    var uuid = UUID.fromString(projectId);
    Session session = sessions.get(uuid);
    if (session != null && session.isOpen()) {
      session.getAsyncRemote().sendText(content);
    }
  }
}
