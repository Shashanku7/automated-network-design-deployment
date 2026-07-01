package org.acme.gateway.entities;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

@Entity
@Table(name = "projects")
public class ProjectEntity {
  @Id
  @GeneratedValue
  private UUID id;

  @Column(nullable = false)
  private String title;

  @Column(name = "solution_type")
  private String solutionType;

  @Column(columnDefinition = "TEXT")
  private String requirements;

  @Column(name = "chat_history", columnDefinition = "TEXT")
  private String chatHistory;

  @Column(name = "workflow_status")
  private String workflowStatus;

  @Column(name = "user_id", nullable = false)
  private String userId;

  @CreationTimestamp
  @Column(name = "created_at", nullable = false)
  private OffsetDateTime createdAt;

  @UpdateTimestamp
  @Column(name = "updated_at", nullable = false)
  private OffsetDateTime updatedAt;

  public ProjectEntity() {}

  public ProjectEntity(String title, String userId) {
    this.title = title;
    this.userId = userId;
  }

  public UUID getId() { return id; }
  public void setId(UUID id) { this.id = id; }
  public String getTitle() { return title; }
  public void setTitle(String title) { this.title = title; }
  public String getSolutionType() { return solutionType; }
  public void setSolutionType(String solutionType) { this.solutionType = solutionType; }
  public String getRequirements() { return requirements; }
  public void setRequirements(String requirements) { this.requirements = requirements; }
  public String getChatHistory() { return chatHistory; }
  public void setChatHistory(String chatHistory) { this.chatHistory = chatHistory; }
  public String getWorkflowStatus() { return workflowStatus; }
  public void setWorkflowStatus(String workflowStatus) { this.workflowStatus = workflowStatus; }
  public String getUserId() { return userId; }
  public void setUserId(String userId) { this.userId = userId; }
  public OffsetDateTime getCreatedAt() { return createdAt; }
  public OffsetDateTime getUpdatedAt() { return updatedAt; }
}
