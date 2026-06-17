package org.acme.gateway.repositories;

import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.List;
import java.util.UUID;
import org.acme.gateway.entities.ConversationEntity;

@ApplicationScoped
public class ConversationRepository implements PanacheRepositoryBase<ConversationEntity, UUID> {
  public List<ConversationEntity> findByProjectId(UUID projectId) {
    return list("projectId", projectId);
  }
}
