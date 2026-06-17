package org.acme.gateway.repositories;

import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.List;
import java.util.UUID;
import org.acme.gateway.entities.MessageEntity;

@ApplicationScoped
public class MessageRepository implements PanacheRepositoryBase<MessageEntity, UUID> {
  public List<MessageEntity> findByConversationIdOrdered(UUID conversationId) {
    return list("conversationId order by sequenceNo", conversationId);
  }

  public long countByConversationId(UUID conversationId) {
    return count("conversationId", conversationId);
  }
}
