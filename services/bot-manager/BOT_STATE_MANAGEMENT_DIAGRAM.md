# Bot State Management Architecture Diagram

## System Overview

```mermaid
graph TB
    %% External Components
    User[👤 User/API Client]
    AdminAPI[🏢 Admin API]
    
    %% Core Services
    BotManager[🤖 Bot Manager Service]
    VexaBot[🕷️ Vexa Bot Service]
    WhisperLive[🎤 WhisperLive Service]
    
    %% Data Stores
    PostgreSQL[(🗄️ PostgreSQL Database)]
    Redis[(🔴 Redis)]
    
    %% Infrastructure
    Docker[Docker Engine]
    Nomad[Nomad Orchestrator]
    
    %% External Platforms
    GoogleMeet[📹 Google Meet]
    Zoom[📹 Zoom]
    Teams[📹 Microsoft Teams]
    
    %% Connections
    User --> BotManager
    AdminAPI --> BotManager
    BotManager --> PostgreSQL
    BotManager --> Redis
    BotManager --> Docker
    BotManager --> Nomad
    VexaBot --> Redis
    VexaBot --> WhisperLive
    VexaBot --> GoogleMeet
    VexaBot --> Zoom
    VexaBot --> Teams
    Docker --> VexaBot
    Nomad --> VexaBot
```

## Bot Lifecycle State Flow

```mermaid
stateDiagram-v2
    [*] --> Requested: User requests bot
    
    Requested --> Starting: Container creation started
    Starting --> Active: Bot successfully started
    Starting --> Error: Container creation failed
    
    Active --> Stopping: Stop command received
    Active --> Reconfiguring: Reconfigure command received
    Reconfiguring --> Active: Reconfiguration complete
    
    Stopping --> Completed: Bot exited successfully
    Stopping --> Failed: Bot exited with error
    Stopping --> Error: Stop process failed
    
    Error --> [*]: Cleanup complete
    Completed --> [*]: Post-meeting tasks
    Failed --> [*]: Post-meeting tasks
```

## Redis Pub/Sub Communication

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant BM as 🤖 Bot Manager
    participant Redis as 🔴 Redis
    participant VB as 🕷️ Vexa Bot
    participant Platform as 📹 Meeting Platform
    
    Note over User,Platform: Bot Startup Phase
    User->>BM: Start bot request
    BM->>BM: Create meeting record (status: requested)
    BM->>Docker: Create & start container
    BM->>BM: Update status to 'starting'
    VB->>BM: Bot started callback
    BM->>BM: Update status to 'active'
    
    Note over User,Platform: Runtime Communication
    User->>BM: Reconfigure bot
    BM->>Redis: Publish reconfigure command
    Redis->>VB: Deliver command
    VB->>VB: Update internal state
    VB->>Platform: Apply new configuration
    
    User->>BM: Stop bot
    BM->>Redis: Publish leave command
    Redis->>VB: Deliver command
    VB->>Platform: Leave meeting gracefully
    VB->>BM: Bot exit callback
    BM->>BM: Update status to 'completed'/'failed'
```

## Database Schema & State Storage

```mermaid
erDiagram
    USERS {
        int id PK
        string email
        string name
        int max_concurrent_bots
        jsonb data
        timestamp created_at
    }
    
    MEETINGS {
        int id PK
        int user_id FK
        string platform
        string platform_specific_id
        string status
        string bot_container_id
        timestamp start_time
        timestamp end_time
        jsonb data
        timestamp created_at
        timestamp updated_at
    }
    
    MEETING_SESSIONS {
        int id PK
        int meeting_id FK
        string session_uid
        timestamp session_start_time
    }
    
    TRANSCRIPTIONS {
        int id PK
        int meeting_id FK
        float start_time
        float end_time
        string text
        string speaker
        string language
        string session_uid
        timestamp created_at
    }
    
    USERS ||--o{ MEETINGS : has
    MEETINGS ||--o{ MEETING_SESSIONS : contains
    MEETINGS ||--o{ TRANSCRIPTIONS : generates
```

## Container Orchestration & State Management

```mermaid
graph LR
    %% Bot Manager Layer
    subgraph "Bot Manager Service"
        API[API Endpoints]
        DockerUtils[Docker Utils]
        Orchestrator[Orchestrator Interface]
    end
    
    %% Container Management
    subgraph "Container Lifecycle"
        Create[Create Container]
        Start[Start Container]
        Monitor[Monitor Status]
        Stop[Stop Container]
    end
    
    %% State Tracking
    subgraph "State Management"
        DB[Database State]
        RedisPubSub[Redis Pub/Sub]
        Callbacks[Bot Callbacks]
    end
    
    %% Infrastructure
    subgraph "Infrastructure"
        Docker[Docker Engine]
        Nomad[Nomad]
        Redis[Redis]
        PostgreSQL[PostgreSQL]
    end
    
    API --> DockerUtils
    DockerUtils --> Orchestrator
    Orchestrator --> Create
    Create --> Start
    Start --> Monitor
    Monitor --> Stop
    
    Create --> DB
    Start --> DB
    Stop --> DB
    
    Create --> RedisPubSub
    Start --> Callbacks
    Stop --> Callbacks
    
    Orchestrator --> Docker
    Orchestrator --> Nomad
    DockerUtils --> Redis
    DockerUtils --> PostgreSQL
```

## Redis Channel Structure

```mermaid
graph TD
    %% Redis Channels
    subgraph "Redis Pub/Sub Channels"
        BotCommands[bot_commands:{connection_id}]
        Reconfigure[reconfigure command]
        Leave[leave command]
    end
    
    %% Message Flow
    BotManager[Bot Manager] -->|Publishes| BotCommands
    BotCommands -->|Delivers| VexaBot[Vexa Bot]
    
    %% Command Types
    Reconfigure -->|action: reconfigure<br/>language: en<br/>task: transcribe| BotCommands
    Leave -->|action: leave| BotCommands
    
    %% Subscription Pattern
    VexaBot -->|Subscribes to| BotCommands
    VexaBot -->|Processes| Reconfigure
    VexaBot -->|Processes| Leave
```

## Error Handling & State Recovery

```mermaid
flowchart TD
    Start([Bot Operation]) --> Check{Check State}
    
    Check -->|Normal| Continue[Continue Operation]
    Check -->|Error| ErrorHandler[Error Handler]
    
    ErrorHandler --> LogError[Log Error]
    LogError --> UpdateStatus[Update DB Status]
    UpdateStatus --> ScheduleCleanup[Schedule Cleanup]
    ScheduleCleanup --> Retry{Retry Possible?}
    
    Retry -->|Yes| RetryOperation[Retry Operation]
    Retry -->|No| MarkFailed[Mark as Failed]
    
    RetryOperation --> Check
    MarkFailed --> PostMeetingTasks[Run Post-Meeting Tasks]
    
    Continue --> Success{Operation Success?}
    Success -->|Yes| UpdateSuccess[Update Success State]
    Success -->|No| ErrorHandler
    
    UpdateSuccess --> PostMeetingTasks
    PostMeetingTasks --> End([End])
```

## Key Components Summary

### **Bot Manager Service**
- **State Persistence**: PostgreSQL database
- **Real-time Communication**: Redis Pub/Sub
- **Container Orchestration**: Docker/Nomad integration
- **API Management**: RESTful endpoints for bot control

### **Vexa Bot Service**
- **Command Reception**: Redis subscription to command channels
- **State Synchronization**: Callbacks to bot-manager
- **Platform Integration**: Meeting platform automation
- **Configuration Management**: Runtime reconfiguration support

### **State Management**
- **Database**: Persistent meeting and session state
- **Redis**: Real-time command delivery
- **Docker**: Container lifecycle tracking
- **Callbacks**: Bidirectional state synchronization

### **Key Features**
- ✅ **Real-time Control**: Redis Pub/Sub for immediate bot commands
- ✅ **State Persistence**: PostgreSQL for reliable state storage
- ✅ **Lifecycle Management**: Complete bot startup/shutdown flow
- ✅ **Error Recovery**: Robust error handling and state recovery
- ✅ **Multi-platform**: Support for Google Meet, Zoom, Teams
- ✅ **Runtime Reconfiguration**: Dynamic language and task updates

