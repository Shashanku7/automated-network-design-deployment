package org.acme.gateway.entities;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

@Entity
@Table(name = "agent_tasks")
public class AgentTaskEntity {
  @Id
  @Column(name = "task_id")
  private UUID taskId;

  @Column(name = "conversation_id", nullable = false)
  private UUID conversationId;

  @Column(name = "project_id", nullable = false)
  private UUID projectId;

  @Column(nullable = false)
  private int phase;

  @Column(name = "agent_target")
  private String agentTarget;

  @Column(name = "input_context", columnDefinition = "TEXT")
  private String inputContext;

  @Column(columnDefinition = "TEXT")
  private String output;

  @Column(nullable = false)
  private String status;

  @CreationTimestamp
  @Column(name = "started_at", nullable = false)
  private OffsetDateTime startedAt;

  @Column(name = "completed_at")
  private OffsetDateTime completedAt;

  public AgentTaskEntity() {}

  public AgentTaskEntity(UUID taskId, UUID conversationId, UUID projectId, int phase, String agentTarget, String inputContext) {
    this.taskId = taskId;
    this.conversationId = conversationId;
    this.projectId = projectId;
    this.phase = phase;
    this.agentTarget = agentTarget;
    this.inputContext = inputContext;
    this.status = "pending";
  }

  public UUID getTaskId() { return taskId; }
  public void setTaskId(UUID taskId) { this.taskId = taskId; }
  public UUID getConversationId() { return conversationId; }
  public UUID getProjectId() { return projectId; }
  public int getPhase() { return phase; }
  public String getAgentTarget() { return agentTarget; }
  public String getOutput() { return output; }
  public void setOutput(String output) { this.output = output; }
  public String getStatus() { return status; }
  public void setStatus(String status) { this.status = status; }
  public OffsetDateTime getCompletedAt() { return completedAt; }
  public void setCompletedAt(OffsetDateTime completedAt) { this.completedAt = completedAt; }
}
