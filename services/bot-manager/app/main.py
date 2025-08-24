import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import os
import base64
from typing import Optional, List, Dict, Any
import redis.asyncio as aioredis
import asyncio
import json
import httpx

from .config import BOT_IMAGE_NAME, REDIS_URL
from app.orchestrators import (
    get_socket_session, close_docker_client, start_bot_container,
    stop_bot_container, _record_session_start, get_running_bots_status,
    verify_container_running,
)
from shared_models.database import init_db, get_db, async_session_local
from shared_models.models import User, Meeting, MeetingSession, Transcription
from shared_models.schemas import MeetingCreate, MeetingResponse, Platform, BotStatusResponse
from app.auth import get_user_and_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from datetime import datetime, timedelta

from app.tasks.bot_exit_tasks import run_all_tasks

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bot_manager")

# Initialize the FastAPI app
app = FastAPI(title="Vexa Bot Manager")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Client Global
redis_client: Optional[aioredis.Redis] = None

# Pydantic models
class MeetingConfigUpdate(BaseModel):
    language: Optional[str] = Field(None, description="New language code (e.g., 'en', 'es')")
    task: Optional[str] = Field(None, description="New task ('transcribe' or 'translate')")

class BotExitCallbackPayload(BaseModel):
    connection_id: str = Field(..., description="The connectionId (session_uid) of the exiting bot.")
    exit_code: int = Field(..., description="The exit code of the bot process (0 for success, 1 for UI leave failure).")
    reason: Optional[str] = Field("self_initiated_leave", description="Reason for the exit.")

class BotStartedCallbackPayload(BaseModel):
    connection_id: str = Field(..., description="The connectionId (session_uid) of the started bot.")
    status: str = Field(..., description="Status of the bot (e.g., 'joined_meeting', 'recording_started').")
    details: Optional[str] = Field(None, description="Additional details about the bot status.")

class BotJoinedCallbackPayload(BaseModel):
    connection_id: str = Field(..., description="The connectionId (session_uid) of the joined bot.")

class BotHeartbeatCallbackPayload(BaseModel):
    connection_id: str = Field(..., description="The connectionId (session_uid) of the bot.")

class BotStatusUpdatePayload(BaseModel):
    connection_id: str = Field(..., description="The connectionId (session_uid) of the bot.")
    status: str = Field(..., description="New status to set.")

# --- Bot Management Endpoints ---

@app.post("/bots",
         status_code=status.HTTP_202_ACCEPTED,
          summary="Request a new bot to join a meeting",
          description="Reserves a meeting slot and launches a bot instance. Bot will manage its own state transitions.",
          response_model=MeetingResponse)
async def request_bot(
    req: MeetingCreate,
    auth_data: tuple[str, User] = Depends(get_user_and_token),
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot Manager only reserves slot and starts container.
    Bot will manage all state transitions via callbacks.
    """
    user_token, current_user = auth_data
    platform = req.platform  # Keep as Platform enum object
    native_meeting_id = req.native_meeting_id
    language = req.language or "en"
    task = req.task or "transcribe"
    
    logger.info(f"User {current_user.id} requesting bot for {platform}/{native_meeting_id}")
    
    # PHASE 1: Check concurrent bot limit and reserve slot
    # Lock user row to check concurrent bots
        user_stmt = select(User).where(User.id == current_user.id).with_for_update()
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    # Count active meetings (reserved, starting, active)
    active_count_stmt = select(func.count(Meeting.id)).where(
        and_(
            Meeting.user_id == current_user.id,
            Meeting.status.in_(['reserved', 'starting', 'active'])
        )
    )
    active_count_result = await db.execute(active_count_stmt)
    active_count = active_count_result.scalar()
        
    if active_count >= user.max_concurrent_bots:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum concurrent bots limit reached ({user.max_concurrent_bots})"
            )
        
    # Create meeting record with 'reserved' status
        meeting = Meeting(
            user_id=current_user.id,
            platform=platform,
            platform_specific_id=native_meeting_id,
        status='reserved',  # Bot Manager sets initial status only
        start_time=None,  # Bot will set this
        end_time=None,    # Bot will set this
        data={}  # Bot will populate this
    )
        db.add(meeting)
    await db.flush()  # Get the meeting ID
    await db.refresh(meeting)
    
    logger.info(f"Reserved meeting slot {meeting.id} for user {current_user.id}")

    # PHASE 2: Start bot container
    try:
        # Construct meeting URL from platform and native_meeting_id
        meeting_url = platform.construct_meeting_url(native_meeting_id)
        if not meeting_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not construct meeting URL for platform {platform.value} and meeting ID {native_meeting_id}"
            )
        
        container_id, connection_id = await start_bot_container(
            user_id=current_user.id,
            meeting_id=meeting.id,
            meeting_url=meeting_url,
            platform=platform.value,
            bot_name=req.bot_name,
            user_token=user_token,
            native_meeting_id=native_meeting_id,
            language=language,
            task=task
        )
        
        if not container_id or not connection_id:
            raise Exception("Failed to start bot container")
        
        # Update container ID (Bot Manager can still set this)
            meeting.bot_container_id = container_id
            await db.commit()
        
        logger.info(f"Successfully started bot container {container_id} for meeting {meeting.id}")
        
        # Return the meeting response
        return MeetingResponse(
            id=meeting.id,
            user_id=meeting.user_id,
            platform=meeting.platform,
            native_meeting_id=meeting.platform_specific_id,
            status=meeting.status,
            bot_container_id=meeting.bot_container_id,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            data=meeting.data,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot for meeting {meeting.id}: {e}", exc_info=True)
        # Mark meeting as failed if container start fails
            meeting.status = 'failed'
            meeting.end_time = datetime.utcnow()
            await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start bot container"
        )

@app.put("/bots/{platform}/{native_meeting_id}/config",
         status_code=status.HTTP_202_ACCEPTED,
         summary="Update configuration for an active bot",
         description="Sends a reconfiguration command via Redis Pub/Sub. Bot will handle the state change.",
         dependencies=[Depends(get_user_and_token)])
async def update_bot_config(
    platform: Platform,
    native_meeting_id: str,
    req: MeetingConfigUpdate,
    auth_data: tuple[str, User] = Depends(get_user_and_token),
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot Manager only publishes commands, never writes status.
    Bot will handle reconfiguration and update its own state.
    """
    global redis_client
    user_token, current_user = auth_data

    logger.info(f"User {current_user.id} requesting config update for {platform.value}/{native_meeting_id}")

    # Find the active meeting for this user/platform/native_id
    active_meeting_stmt = select(Meeting).where(
        Meeting.user_id == current_user.id,
        Meeting.platform == platform.value,
        Meeting.platform_specific_id == native_meeting_id,
        Meeting.status == 'active'  # Only active bots can be reconfigured
    ).order_by(Meeting.created_at.desc())
    
    result = await db.execute(active_meeting_stmt)
    active_meeting = result.scalars().first()

    if not active_meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active meeting found for platform {platform.value} and meeting ID {native_meeting_id}"
        )

    # Find the session UID for this meeting
    session_stmt = select(MeetingSession.session_uid).where(
        MeetingSession.meeting_id == active_meeting.id
    ).order_by(MeetingSession.session_start_time.asc()).limit(1)
    
    session_result = await db.execute(session_stmt)
    session_uid = session_result.scalars().first()

    if not session_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meeting is active but session information is missing"
        )

    # Publish reconfiguration command via Redis
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to internal messaging service"
        )

    command_payload = {
        "action": "reconfigure",
        "language": req.language,
        "task": req.task
    }
    channel = f"bot_commands:{session_uid}"

    try:
        payload_str = json.dumps(command_payload)
        logger.info(f"Publishing reconfigure command to channel '{channel}': {payload_str}")
        await redis_client.publish(channel, payload_str)
        logger.info(f"Successfully published reconfigure command for session {session_uid}")
    except Exception as e:
        logger.error(f"Failed to publish reconfigure command: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reconfiguration command"
        )

    return {"message": "Reconfiguration request accepted and sent to the bot"}

@app.delete("/bots/{platform}/{native_meeting_id}",
             status_code=status.HTTP_202_ACCEPTED,
           summary="Stop a bot for a specific meeting",
           description="Sends a leave command via Redis Pub/Sub. Bot will handle graceful shutdown and state update.",
           response_model=MeetingResponse,
             dependencies=[Depends(get_user_and_token)])
async def stop_bot(
    platform: Platform,
    native_meeting_id: str,
    auth_data: tuple[str, User] = Depends(get_user_and_token),
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot Manager only publishes leave command, never writes status.
    Bot will handle graceful shutdown and update its own state.
    """
    global redis_client
    user_token, current_user = auth_data

    logger.info(f"User {current_user.id} requesting bot stop for {platform.value}/{native_meeting_id}")

    # Find the active meeting
    meeting_stmt = select(Meeting).where(
        Meeting.user_id == current_user.id,
        Meeting.platform == platform.value,
        Meeting.platform_specific_id == native_meeting_id,
        Meeting.status.in_(['active', 'starting'])  # Can stop active or starting bots
    ).order_by(Meeting.created_at.desc())

    result = await db.execute(meeting_stmt)
    meeting = result.scalars().first()

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active meeting found for platform {platform.value} and meeting ID {native_meeting_id}"
        )

    # Find the session UID
    session_stmt = select(MeetingSession.session_uid).where(
        MeetingSession.meeting_id == meeting.id
    ).order_by(MeetingSession.session_start_time.asc()).limit(1)

    session_result = await db.execute(session_stmt)
    session_uid = session_result.scalars().first()

    if not session_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meeting found but session information is missing"
        )

    # Publish leave command via Redis
    if not redis_client:
        logger.error("Redis client not available. Cannot send leave command.")
        # Still return success since the command was received
    else:
        try:
            command_channel = f"bot_commands:{session_uid}"
            payload = json.dumps({"action": "leave"})
            logger.info(f"Publishing leave command to Redis channel '{command_channel}': {payload}")
            await redis_client.publish(command_channel, payload)
            logger.info(f"Successfully published leave command for session {session_uid}")
        except Exception as e:
            logger.error(f"Failed to publish leave command: {e}", exc_info=True)

    # Schedule delayed container cleanup as backup
    if meeting.bot_container_id:
        background_tasks = BackgroundTasks()
    background_tasks.add_task(_delayed_container_stop, meeting.bot_container_id, 30) 

    return {"message": "Stop request accepted and is being processed"}

@app.get("/bots/status",
         response_model=BotStatusResponse,
         summary="Get status of running bot containers for the authenticated user",
         dependencies=[Depends(get_user_and_token)])
async def get_user_bots_status(
    auth_data: tuple[str, User] = Depends(get_user_and_token)
):
    """Retrieves a list of currently running bot containers associated with the user's API key."""
    user_token, current_user = auth_data
    user_id = current_user.id
    
    logger.info(f"Fetching running bot status for user {user_id}")
    
    try:
        running_bots_list = await get_running_bots_status(user_id)
        return BotStatusResponse(running_bots=running_bots_list)
    except Exception as e:
        logger.error(f"Error fetching bot status for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bot status"
        )

# --- Bot Callback Endpoints (State Owners) ---

@app.post("/bots/internal/callback/started",
          status_code=status.HTTP_200_OK,
          summary="Bot started callback - Bot sets status to 'starting'",
          include_in_schema=False)
async def bot_started_callback(
    payload: BotStartedCallbackPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot owns this state transition.
    Bot Manager only updates the database, never decides the status.
    """
    logger.info(f"Received bot started callback: connection_id={payload.connection_id}, status={payload.status}")
    
    session_uid = payload.connection_id

    try:
        # Find the meeting session to get the meeting_id
        session_stmt = select(MeetingSession).where(MeetingSession.session_uid == session_uid)
        session_result = await db.execute(session_stmt)
        meeting_session = session_result.scalars().first()

        if not meeting_session:
            logger.error(f"Bot started callback: Could not find meeting session for connection_id {session_uid}")
            return {"status": "error", "detail": "Meeting session not found"}

        meeting_id = meeting_session.meeting_id
        logger.info(f"Bot started callback: Found meeting_id {meeting_id} for connection_id {session_uid}")

        # Update meeting status to 'starting' (Bot decides this)
        async with db.begin():
            meeting = await db.get(Meeting, meeting_id)
            if meeting and meeting.status == 'reserved':
                meeting.status = 'starting'
                meeting.start_time = datetime.utcnow()
                await db.commit()
                logger.info(f"Bot started callback: Meeting {meeting_id} status updated to 'starting'")
            else:
                logger.warning(f"Bot started callback: Meeting {meeting_id} not found or wrong status ({meeting.status if meeting else 'None'})")

        return {"status": "callback processed", "meeting_id": meeting_id, "new_status": "starting"}

    except Exception as e:
        logger.error(f"Bot started callback: An unexpected error occurred: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the bot started callback"
        )

@app.post("/bots/internal/callback/joined",
          status_code=status.HTTP_200_OK,
          summary="Bot joined meeting callback - Bot sets status to 'active'",
          include_in_schema=False)
async def bot_joined_callback(
    payload: BotJoinedCallbackPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot owns this state transition.
    Bot Manager only updates the database, never decides the status.
    """
    logger.info(f"Received bot joined callback: connection_id={payload.connection_id}")
    
    session_uid = payload.connection_id

    try:
        # Find the meeting session to get the meeting_id
        session_stmt = select(MeetingSession).where(MeetingSession.session_uid == session_uid)
        session_result = await db.execute(session_stmt)
        meeting_session = session_result.scalars().first()

        if not meeting_session:
            logger.error(f"Bot joined callback: Could not find meeting session for connection_id {session_uid}")
            return {"status": "error", "detail": "Meeting session not found"}

        meeting_id = meeting_session.meeting_id
        logger.info(f"Bot joined callback: Found meeting_id {meeting_id} for connection_id {session_uid}")

        # Update meeting status to 'active' (Bot decides this)
        async with db.begin():
            meeting = await db.get(Meeting, meeting_id)
            if meeting and meeting.status == 'starting':
                meeting.status = 'active'
                await db.commit()
                logger.info(f"Bot joined callback: Meeting {meeting_id} status updated to 'active'")
            else:
                logger.warning(f"Bot joined callback: Meeting {meeting_id} not found or wrong status ({meeting.status if meeting else 'None'})")

        return {"status": "callback processed", "meeting_id": meeting_id, "new_status": "active"}

    except Exception as e:
        logger.error(f"Bot joined callback: An unexpected error occurred: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the bot joined callback"
        )

@app.post("/bots/internal/callback/exited",
          status_code=status.HTTP_200_OK,
          summary="Bot exit callback - Bot sets final status",
          include_in_schema=False)
async def bot_exit_callback(
    payload: BotExitCallbackPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot owns this state transition.
    Bot Manager only updates the database, never decides the status.
    """
    logger.info(f"Received bot exit callback: connection_id={payload.connection_id}, exit_code={payload.exit_code}, reason={payload.reason}")
    
    session_uid = payload.connection_id
    exit_code = payload.exit_code

    try:
        # Find the meeting session to get the meeting_id
        session_stmt = select(MeetingSession).where(MeetingSession.session_uid == session_uid)
        session_result = await db.execute(session_stmt)
        meeting_session = session_result.scalars().first()

        if not meeting_session:
            logger.error(f"Bot exit callback: Could not find meeting session for connection_id {session_uid}")
            return {"status": "error", "detail": "Meeting session not found"}

        meeting_id = meeting_session.meeting_id
        logger.info(f"Bot exit callback: Found meeting_id {meeting_id} for connection_id {session_uid}")

        # Update meeting status based on exit code (Bot decides this)
        meeting = await db.get(Meeting, meeting_id)
        if not meeting:
            logger.error(f"Bot exit callback: Could not find meeting {meeting_id}")
            return {"status": "error", "detail": f"Meeting {meeting_id} not found"}

        # Bot decides the final status
        if exit_code == 0:
            meeting.status = 'completed'
            logger.info(f"Bot exit callback: Meeting {meeting_id} status updated to 'completed'")
        else:
            meeting.status = 'failed'
            logger.warning(f"Bot exit callback: Meeting {meeting_id} status updated to 'failed' due to exit_code {exit_code}")
        
        meeting.end_time = datetime.utcnow()
        await db.commit()
        logger.info(f"Bot exit callback: Meeting {meeting_id} successfully updated in DB")

        # Schedule post-meeting tasks
        background_tasks.add_task(run_all_tasks, meeting_id)

        return {"status": "callback processed", "meeting_id": meeting_id, "final_status": meeting.status}

    except Exception as e:
        logger.error(f"Bot exit callback: An unexpected error occurred: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the bot exit callback"
        )

@app.post("/bots/internal/callback/heartbeat",
          status_code=status.HTTP_200_OK,
          summary="Bot heartbeat callback - Updates last activity",
          include_in_schema=False)
async def bot_heartbeat_callback(
    payload: BotHeartbeatCallbackPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot sends heartbeat to maintain liveness.
    Uses existing updated_at field instead of adding new field.
    """
    logger.info(f"Received bot heartbeat: connection_id={payload.connection_id}")
    
    session_uid = payload.connection_id

    try:
        # Find the meeting session to get the meeting_id
        session_stmt = select(MeetingSession).where(MeetingSession.session_uid == session_uid)
        session_result = await db.execute(session_stmt)
        meeting_session = session_result.scalars().first()

        if not meeting_session:
            logger.error(f"Bot heartbeat: Could not find meeting session for connection_id {session_uid}")
            return {"status": "error", "detail": "Meeting session not found"}

        meeting_id = meeting_session.meeting_id

        # Update the updated_at field to track last activity
        meeting = await db.get(Meeting, meeting_id)
        if meeting:
            meeting.updated_at = datetime.utcnow()
            await db.commit()
            logger.debug(f"Bot heartbeat: Updated last activity for meeting {meeting_id}")

        return {"status": "heartbeat processed", "meeting_id": meeting_id}

    except Exception as e:
        logger.error(f"Bot heartbeat: An unexpected error occurred: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the bot heartbeat"
        )

@app.patch("/bots/internal/callback/status",
           status_code=status.HTTP_200_OK,
           summary="Bot status update callback - Bot sets intermediate status",
           include_in_schema=False)
async def bot_status_update_callback(
    payload: BotStatusUpdatePayload,
    db: AsyncSession = Depends(get_db)
):
    """
    REFACTORED: Bot can set intermediate statuses (e.g., 'stopping').
    Bot Manager only updates the database, never decides the status.
    """
    logger.info(f"Received bot status update: connection_id={payload.connection_id}, status={payload.status}")
    
    session_uid = payload.connection_id
    new_status = payload.status

    try:
        # Find the meeting session to get the meeting_id
        session_stmt = select(MeetingSession).where(MeetingSession.session_uid == session_uid)
        session_result = await db.execute(session_stmt)
        meeting_session = session_result.scalars().first()

        if not meeting_session:
            logger.error(f"Bot status update: Could not find meeting session for connection_id {session_uid}")
            return {"status": "error", "detail": "Meeting session not found"}

        meeting_id = meeting_session.meeting_id
        logger.info(f"Bot status update: Found meeting_id {meeting_id} for connection_id {session_uid}")

        # Update meeting status (Bot decides this)
        meeting = await db.get(Meeting, meeting_id)
        if meeting:
            meeting.status = new_status
            meeting.updated_at = datetime.utcnow()
        await db.commit()
            logger.info(f"Bot status update: Meeting {meeting_id} status updated to '{new_status}'")
        else:
            logger.error(f"Bot status update: Could not find meeting {meeting_id}")

        return {"status": "status update processed", "meeting_id": meeting_id, "new_status": new_status}

    except Exception as e:
        logger.error(f"Bot status update: An unexpected error occurred: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the bot status update"
        )

# --- Background Tasks ---

async def _delayed_container_stop(container_id: str, delay_seconds: int = 30):
    """Background task to stop container after delay."""
    logger.info(f"Delayed container stop scheduled for {container_id} in {delay_seconds} seconds")
    await asyncio.sleep(delay_seconds)
    
    try:
        await stop_bot_container(container_id)
        logger.info(f"Successfully stopped container {container_id} after delay")
    except Exception as e:
        logger.error(f"Failed to stop container {container_id} after delay: {e}", exc_info=True)

async def _cleanup_stale_meetings():
    """Background task to clean up stale meetings and ensure system consistency."""
    logger.info("Starting stale meeting cleanup task...")
    
    try:
        async with async_session_local() as db:
            # Check reserved meetings older than 5 minutes
            stale_reserved_cutoff = datetime.utcnow() - timedelta(minutes=5)
            stale_reserved_stmt = select(Meeting).where(
                and_(
                    Meeting.status == 'reserved',
                    Meeting.created_at < stale_reserved_cutoff
                )
            )
            stale_reserved_result = await db.execute(stale_reserved_stmt)
            stale_reserved = stale_reserved_result.scalars().all()
            
            for meeting in stale_reserved:
                logger.warning(f"Marking stale reserved meeting {meeting.id} as failed (older than 5 minutes)")
                meeting.status = 'failed'
                meeting.end_time = datetime.utcnow()
                meeting.data = {**meeting.data, 'failure_reason': 'stale_reserved_timeout'}
            
            # Check starting meetings older than 10 minutes
            stale_starting_cutoff = datetime.utcnow() - timedelta(minutes=10)
            stale_starting_stmt = select(Meeting).where(
                and_(
                    Meeting.status == 'starting',
                    Meeting.start_time < stale_starting_cutoff
                )
            )
            stale_starting_result = await db.execute(stale_starting_stmt)
            stale_starting = stale_starting_result.scalars().all()
            
            for meeting in stale_starting:
                logger.warning(f"Marking stale starting meeting {meeting.id} as failed (older than 10 minutes)")
                meeting.status = 'failed'
                meeting.end_time = datetime.utcnow()
                meeting.data = {**meeting.data, 'failure_reason': 'stale_starting_timeout'}
            
            # Check active meetings with no recent activity (updated_at > 2 minutes old)
            stale_active_cutoff = datetime.utcnow() - timedelta(minutes=2)
            stale_active_stmt = select(Meeting).where(
                and_(
                    Meeting.status == 'active',
                    Meeting.updated_at < stale_active_cutoff
                )
            )
            stale_active_result = await db.execute(stale_active_stmt)
            stale_active = stale_active_result.scalars().all()
            
            for meeting in stale_active:
                logger.warning(f"Marking stale active meeting {meeting.id} as failed (no activity for 2+ minutes)")
                meeting.status = 'failed'
                meeting.end_time = datetime.utcnow()
                meeting.data = {**meeting.data, 'failure_reason': 'stale_active_timeout'}
            
            # Check stopping meetings older than 5 minutes
            stale_stopping_cutoff = datetime.utcnow() - timedelta(minutes=5)
            stale_stopping_stmt = select(Meeting).where(
                and_(
                    Meeting.status == 'stopping',
                    Meeting.updated_at < stale_stopping_cutoff
                )
            )
            stale_stopping_result = await db.execute(stale_stopping_stmt)
            stale_stopping = stale_stopping_result.scalars().all()
            
            for meeting in stale_stopping:
                logger.warning(f"Marking stale stopping meeting {meeting.id} as failed (older than 5 minutes)")
                meeting.status = 'failed'
                meeting.end_time = datetime.utcnow()
                meeting.data = {**meeting.data, 'failure_reason': 'stale_stopping_timeout'}
            
            # Commit all changes
            if any([stale_reserved, stale_starting, stale_active, stale_stopping]):
                await db.commit()
                logger.info(f"Cleanup completed: {len(stale_reserved)} reserved, {len(stale_starting)} starting, {len(stale_active)} active, {len(stale_stopping)} stopping meetings marked as failed")
            else:
                logger.info("No stale meetings found during cleanup")
                
    except Exception as e:
        logger.error(f"Error during stale meeting cleanup: {e}", exc_info=True)
        try:
            await db.rollback()
        except:
            pass

# Start background cleanup task
@app.on_event("startup")
async def startup_event():
    global redis_client
    logger.info("Starting up Bot Manager...")
    try:
        get_socket_session()
    except Exception as e:
        logger.error(f"Failed to initialize Docker client on startup: {e}", exc_info=True)

    # Redis Client Initialization
    try:
        logger.info(f"Connecting to Redis at {REDIS_URL}...")
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis on startup: {e}", exc_info=True)
        redis_client = None

    # Start background cleanup task
    asyncio.create_task(_periodic_cleanup())
    
    logger.info("Database, Docker Client (attempted), Redis Client (attempted), and background cleanup initialized.")

async def _periodic_cleanup():
    """Runs cleanup task every minute."""
    while True:
        try:
            await _cleanup_stale_meetings()
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
        
        # Wait 1 minute before next cleanup
        await asyncio.sleep(60)

# --- Health Check ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bot-manager"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080) 