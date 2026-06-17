package org.acme.gateway;

import module java.base;

import io.smallrye.common.annotation.Blocking;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.websocket.OnClose;
import jakarta.websocket.OnError;
import jakarta.websocket.OnMessage;
import jakarta.websocket.OnOpen;
import jakarta.websocket.Session;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import lombok.extern.java.Log;
import org.acme.gateway.services.KafkaService;

@ServerEndpoint("/chat/{projectId}")
@ApplicationScoped
@Log
public class APIWebSocket {
  @Inject
  KafkaService kafkaService;
  Map<UUID, Session> sessions = new ConcurrentHashMap<>();

  @OnOpen
  public void onOpen(Session session, @PathParam("projectId") String projectId) {
    log.info("WS open projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    sessions.putIfAbsent(uuid, session);
  }

  @OnClose
  public void onClose(Session session, @PathParam("projectId") String projectId) {
    log.info("WS close projectId=" + projectId);
    var uuid = UUID.fromString(projectId);
    sessions.remove(uuid);
  }

  @OnError
  public void OnError(
      Session session, @PathParam("projectId") String projectId, Throwable throwable) {
    log.severe("WS error projectId=" + projectId + " error=" + throwable.getMessage());
    var uuid = UUID.fromString(projectId);
    sessions.remove(uuid);
  }

  @Blocking
  @OnMessage
  public void onMessage(String message, @PathParam("projectId") String projectId) {
    log.info("WS msg projectId=" + projectId + " len=" + message.length() + " preview=" + message.substring(0, Math.min(200, message.length())));
    var uuid = UUID.fromString(projectId);
    kafkaService.sendTask(message, uuid);
  }

  public void sendMessage(String projectId, String content) {
    var uuid = UUID.fromString(projectId);
    Session session = sessions.get(uuid);
    if (session != null && session.isOpen()) {
      log.info("WS send projectId=" + projectId + " len=" + content.length());
      session.getAsyncRemote().sendText(content);
    } else {
      log.warning("WS send fail projectId=" + projectId + " session=" + (session == null ? "null" : "closed"));
    }
  }
}
