package org.acme.gateway.repositories;

import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.acme.gateway.entities.AgentTaskEntity;

@ApplicationScoped
public class AgentTaskRepository implements PanacheRepositoryBase<AgentTaskEntity, UUID> {
  public Optional<AgentTaskEntity> findLatestByProjectId(UUID projectId) {
    return find("projectId order by startedAt desc").firstResultOptional();
  }

  public List<AgentTaskEntity> findCompletedByProjectId(UUID projectId) {
    return list("projectId = ?1 and status = 'completed' order by phase", projectId);
  }
}
