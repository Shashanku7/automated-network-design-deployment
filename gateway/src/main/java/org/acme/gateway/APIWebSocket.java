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
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.acme.gateway.services.KafkaService;

@ServerEndpoint("/chat/{projectId}")
@ApplicationScoped
public class APIWebSocket {
  @Inject KafkaService kafkaService;
  private Map<UUID, Session> sessions = new ConcurrentHashMap<>();

  @OnOpen
  public void onOpen(Session session, @PathParam("projectId") UUID projectId) {
    sessions.putIfAbsent(projectId, session);
  }

  @OnClose
  public void onClose(Session session, @PathParam("projectId") UUID projectId) {
    sessions.remove(projectId);
  }

  @OnError
  public void OnError(
      Session session, @PathParam("projectId") UUID projectId, Throwable throwable) {
    sessions.remove(projectId);
  }

  @OnMessage
  public void onMessage(String message, @PathParam("projectId") UUID projectId) {
    kafkaService.sendTask(message, projectId);
  }

  public void sendMessage(UUID projectId, String content) {
    Session session = sessions.get(projectId);
    if (session != null && session.isOpen()) {
      session.getAsyncRemote().sendText(content);
    }
  }
}
