package org.acme.gateway.entities;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

@Entity
@Table(name = "messages")
public class MessageEntity {
  @Id
  @GeneratedValue
  private UUID id;

  @Column(name = "conversation_id", nullable = false)
  private UUID conversationId;

  @Column(name = "sequence_no", nullable = false)
  private Long sequenceNo;

  @Column(name = "role", nullable = false)
  private String role;

  @Column(name = "content", nullable = false, columnDefinition = "TEXT")
  private String content;

  @CreationTimestamp
  @Column(name = "created_at", nullable = false)
  private OffsetDateTime createdAt;

  public MessageEntity() {}

  public MessageEntity(UUID conversationId, Long sequenceNo, String role, String content) {
    this.conversationId = conversationId;
    this.sequenceNo = sequenceNo;
    this.role = role;
    this.content = content;
  }

  public UUID getId() { return id; }
  public void setId(UUID id) { this.id = id; }
  public UUID getConversationId() { return conversationId; }
  public void setConversationId(UUID conversationId) { this.conversationId = conversationId; }
  public Long getSequenceNo() { return sequenceNo; }
  public void setSequenceNo(Long sequenceNo) { this.sequenceNo = sequenceNo; }
  public String getRole() { return role; }
  public void setRole(String role) { this.role = role; }
  public String getContent() { return content; }
  public void setContent(String content) { this.content = content; }
  public OffsetDateTime getCreatedAt() { return createdAt; }
}
