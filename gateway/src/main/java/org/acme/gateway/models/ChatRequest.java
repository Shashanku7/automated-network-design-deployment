package org.acme.gateway.models;

import java.util.List;
import java.util.Map;

public class ChatRequest {
    public String message;
    public List<Map<String, String>> history;
    public String screenContext;
}
