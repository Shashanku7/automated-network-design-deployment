package org.acme.gateway.repositories;

import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.UUID;
import org.acme.gateway.entities.ProjectEntity;

@ApplicationScoped
public class ProjectRepository implements PanacheRepositoryBase<ProjectEntity, UUID> {
}
