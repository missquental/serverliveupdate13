import sys
import subprocess
import threading
import time
import os
import json
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import urllib.parse
import requests
import sqlite3
from pathlib import Path

# Install required packages
try:
    import streamlit as st
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
    import streamlit as st

try:
    import google.auth
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import Flow
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth", "google-auth-oauthlib", "google-api-python-client"])
    import google.auth
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import Flow

# Predefined OAuth configuration
PREDEFINED_OAUTH_CONFIG = {
    "web": {
        "client_id": "1086578184958-hin4d45sit9ma5psovppiq543eho41sl.apps.googleusercontent.com",
        "project_id": "anjelikakozme",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["https://redirect1x.streamlit.app"]
    }
}

# Initialize database for persistent logs
def init_database():
    """Initialize SQLite database for persistent logs"""
    try:
        db_path = Path("streaming_logs.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaming_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                log_type TEXT NOT NULL,
                message TEXT NOT NULL,
                video_file TEXT,
                stream_key TEXT,
                channel_name TEXT
            )
        ''')
        
        # Create streaming_sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaming_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                video_file TEXT,
                stream_title TEXT,
                stream_description TEXT,
                tags TEXT,
                category TEXT,
                privacy_status TEXT,
                made_for_kids BOOLEAN,
                channel_name TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Create saved_channels table for persistent authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT UNIQUE NOT NULL,
                channel_id TEXT NOT NULL,
                auth_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database initialization error: {e}")

def save_channel_auth(channel_name, channel_id, auth_data):
    """Save channel authentication data persistently"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO saved_channels 
            (channel_name, channel_id, auth_data, created_at, last_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            channel_name,
            channel_id,
            json.dumps(auth_data),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving channel auth: {e}")
        return False

def load_saved_channels():
    """Load saved channel authentication data"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT channel_name, channel_id, auth_data, last_used
            FROM saved_channels 
            ORDER BY last_used DESC
        ''')
        
        channels = []
        for row in cursor.fetchall():
            channel_name, channel_id, auth_data, last_used = row
            channels.append({
                'name': channel_name,
                'id': channel_id,
                'auth': json.loads(auth_data),
                'last_used': last_used
            })
        
        conn.close()
        return channels
    except Exception as e:
        st.error(f"Error loading saved channels: {e}")
        return []

def update_channel_last_used(channel_name):
    """Update last used timestamp for a channel"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE saved_channels 
            SET last_used = ?
            WHERE channel_name = ?
        ''', (datetime.now().isoformat(), channel_name))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error updating channel last used: {e}")

def log_to_database(session_id, log_type, message, video_file=None, stream_key=None, channel_name=None):
    """Log message to database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO streaming_logs 
            (timestamp, session_id, log_type, message, video_file, stream_key, channel_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            session_id,
            log_type,
            message,
            video_file,
            stream_key,
            channel_name
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error logging to database: {e}")

def get_logs_from_database(session_id=None, limit=100):
    """Get logs from database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        if session_id:
            cursor.execute('''
                SELECT timestamp, log_type, message, video_file, channel_name
                FROM streaming_logs 
                WHERE session_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
        else:
            cursor.execute('''
                SELECT timestamp, log_type, message, video_file, channel_name
                FROM streaming_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        logs = cursor.fetchall()
        conn.close()
        return logs
    except Exception as e:
        st.error(f"Error getting logs from database: {e}")
        return []

def save_streaming_session(session_id, video_file, stream_title, stream_description, tags, category, privacy_status, made_for_kids, channel_name):
    """Save streaming session to database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO streaming_sessions 
            (session_id, start_time, video_file, stream_title, stream_description, tags, category, privacy_status, made_for_kids, channel_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            datetime.now().isoformat(),
            video_file,
            stream_title,
            stream_description,
            tags,
            category,
            privacy_status,
            made_for_kids,
            channel_name
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error saving streaming session: {e}")

def load_google_oauth_config(json_file):
    """Load Google OAuth configuration from downloaded JSON file"""
    try:
        config = json.load(json_file)
        if 'web' in config:
            return config['web']
        elif 'installed' in config:
            return config['installed']
        else:
            st.error("Invalid Google OAuth JSON format")
            return None
    except Exception as e:
        st.error(f"Error loading Google OAuth JSON: {e}")
        return None

def generate_auth_url_with_state(client_config, current_app_url):
    """Generate OAuth authorization URL with state parameter"""
    try:
        scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
        encoded_state = urllib.parse.quote(current_app_url)
        
        # Create authorization URL
        auth_url = (
            f"{client_config['auth_uri']}?"
            f"client_id={client_config['client_id']}&"
            f"redirect_uri={urllib.parse.quote(client_config['redirect_uris'][0])}&"
            f"scope={urllib.parse.quote(' '.join(scopes))}&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state={encoded_state}"
        )
        return auth_url
    except Exception as e:
        st.error(f"Error generating auth URL: {e}")
        return None

def exchange_code_for_tokens(client_config, auth_code):
    """Exchange authorization code for access and refresh tokens"""
    try:
        token_data = {
            'client_id': client_config['client_id'],
            'client_secret': client_config['client_secret'],
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': client_config['redirect_uris'][0]
        }
        
        response = requests.post(client_config['token_uri'], data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            return tokens
        else:
            st.error(f"Token exchange failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error exchanging code for tokens: {e}")
        return None

def load_channel_config(json_file):
    """Load channel configuration from JSON file"""
    try:
        config = json.load(json_file)
        return config
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
        return None

def validate_channel_config(config):
    """Validate channel configuration structure"""
    required_fields = ['channels']
    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"
    
    if not isinstance(config['channels'], list):
        return False, "Channels must be a list"
    
    for i, channel in enumerate(config['channels']):
        required_channel_fields = ['name', 'stream_key']
        for field in required_channel_fields:
            if field not in channel:
                return False, f"Channel {i+1} missing required field: {field}"
    
    return True, "Valid configuration"

def create_youtube_service(credentials_dict):
    """Create YouTube API service from credentials"""
    try:
        if 'token' in credentials_dict:
            credentials = Credentials.from_authorized_user_info(credentials_dict)
        else:
            credentials = Credentials(
                token=credentials_dict.get('access_token'),
                refresh_token=credentials_dict.get('refresh_token'),
                token_uri=credentials_dict.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=credentials_dict.get('client_id'),
                client_secret=credentials_dict.get('client_secret'),
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
            )
        service = build('youtube', 'v3', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error creating YouTube service: {e}")
        return None

def get_stream_key_only(service):
    """Get stream key without creating broadcast"""
    try:
        # Create a simple live stream to get stream key
        stream_request = service.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": f"Stream Key Generator - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
                },
                "cdn": {
                    "resolution": "1080p",
                    "frameRate": "30fps",
                    "ingestionType": "rtmp"
                }
            }
        )
        stream_response = stream_request.execute()
        
        return {
            "stream_key": stream_response['cdn']['ingestionInfo']['streamName'],
            "stream_url": stream_response['cdn']['ingestionInfo']['ingestionAddress'],
            "stream_id": stream_response['id']
        }
    except Exception as e:
        st.error(f"Error getting stream key: {e}")
        return None

def get_channel_info(service, channel_id=None):
    """Get channel information from YouTube API"""
    try:
        if channel_id:
            request = service.channels().list(
                part="snippet,statistics",
                id=channel_id
            )
        else:
            request = service.channels().list(
                part="snippet,statistics",
                mine=True
            )
        
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        st.error(f"Error fetching channel info: {e}")
        return []

def create_live_stream(service, title, description, scheduled_start_time, tags=None, category_id="20", privacy_status="public", made_for_kids=False):
    """Create a live stream on YouTube with complete settings"""
    try:
        # Create live stream
        stream_request = service.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": title,
                    "description": description
                },
                "cdn": {
                    "resolution": "1080p",
                    "frameRate": "30fps",
                    "ingestionType": "rtmp"
                }
            }
        )
        stream_response = stream_request.execute()
        
        # Prepare broadcast body
        broadcast_body = {
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": scheduled_start_time.isoformat()
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
                "enableAutoStart": True,  # Auto start live stream
                "enableAutoStop": True    # Auto stop when video ends
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": True,
                "recordFromStart": True,
                "enableContentEncryption": False,
                "enableEmbed": True,
                "enableDvr": True,
                "enableLowLatency": False
            }
        }
        
        # Add tags if provided
        if tags:
            broadcast_body["snippet"]["tags"] = tags
            
        # Add category if provided
        if category_id:
            broadcast_body["snippet"]["categoryId"] = category_id
        
        # Create live broadcast
        broadcast_request = service.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body=broadcast_body
        )
        broadcast_response = broadcast_request.execute()
        
        # Bind stream to broadcast
        bind_request = service.liveBroadcasts().bind(
            part="id,contentDetails",
            id=broadcast_response['id'],
            streamId=stream_response['id']
        )
        bind_response = bind_request.execute()
        
        return {
            "stream_key": stream_response['cdn']['ingestionInfo']['streamName'],
            "stream_url": stream_response['cdn']['ingestionInfo']['ingestionAddress'],
            "broadcast_id": broadcast_response['id'],
            "stream_id": stream_response['id'],
            "watch_url": f"https://www.youtube.com/watch?v={broadcast_response['id']}",
            "studio_url": f"https://studio.youtube.com/video/{broadcast_response['id']}/livestreaming",
            "broadcast_response": broadcast_response
        }
    except Exception as e:
        st.error(f"Error creating live stream: {e}")
        return None

def get_existing_broadcasts(service, max_results=10):
    """Get existing live broadcasts"""
    try:
        request = service.liveBroadcasts().list(
            part="snippet,status,contentDetails",
            mine=True,
            maxResults=max_results,
            broadcastStatus="all"
        )
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        st.error(f"Error getting existing broadcasts: {e}")
        return []

def get_broadcast_stream_key(service, broadcast_id):
    """Get stream key for existing broadcast"""
    try:
        # Get broadcast details
        broadcast_request = service.liveBroadcasts().list(
            part="contentDetails",
            id=broadcast_id
        )
        broadcast_response = broadcast_request.execute()
        
        if not broadcast_response['items']:
            return None
            
        stream_id = broadcast_response['items'][0]['contentDetails'].get('boundStreamId')
        
        if not stream_id:
            return None
            
        # Get stream details
        stream_request = service.liveStreams().list(
            part="cdn",
            id=stream_id
        )
        stream_response = stream_request.execute()
        
        if stream_response['items']:
            stream_info = stream_response['items'][0]['cdn']['ingestionInfo']
            return {
                "stream_key": stream_info['streamName'],
                "stream_url": stream_info['ingestionAddress'],
                "stream_id": stream_id
            }
        
        return None
    except Exception as e:
        st.error(f"Error getting broadcast stream key: {e}")
        return None

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        st.warning(f"Tidak dapat membaca durasi video: {e}")
        return None

def run_ffmpeg(video_path, stream_key, is_shorts, log_callback, rtmp_url=None, session_id=None, duration_limit=None, video_settings=None, batch_index=0):
    """Run FFmpeg for streaming with optional duration limit and custom video settings."""
    output_url = rtmp_url or f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
    
    # Default video settings
    if video_settings is None:
        video_settings = {
            "resolution": "1080p",
            "bitrate": "2500k",
            "fps": "30",
            "codec": "libx264",
            "audio_bitrate": "128k",
            "audio_codec": "aac"
        }
    
    # Build FFmpeg command with custom settings
    cmd = [
        "ffmpeg", "-re", "-stream_loop", "-1", "-i", video_path,
        "-c:v", video_settings["codec"], "-preset", "veryfast", 
        "-b:v", video_settings["bitrate"], "-maxrate", video_settings["bitrate"],
        "-bufsize", str(int(video_settings["bitrate"].replace('k', '')) * 2) + "k",
        "-r", video_settings["fps"], "-g", str(int(video_settings["fps"]) * 2),
        "-keyint_min", str(int(video_settings["fps"]) * 2),
        "-c:a", video_settings["audio_codec"], "-b:a", video_settings["audio_bitrate"],
        "-f", "flv"
    ]
    
    # Add scaling for Shorts mode if enabled
    if is_shorts:
        cmd.extend(["-vf", "scale=720:1280"])
    
    # Add duration limit if specified
    if duration_limit:
        cmd.insert(1, str(duration_limit))
        cmd.insert(1, "-t")
    
    cmd.append(output_url)
    
    start_msg = f"🚀 Batch {batch_index}: Starting FFmpeg with settings: {' '.join(cmd[:8])}... [RTMP URL hidden for security]"
    log_callback(start_msg)
    if session_id:
        log_to_database(session_id, "INFO", f"Batch {batch_index}: {start_msg}", video_path)
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            log_callback(f"Batch {batch_index}: {line.strip()}")
            if session_id:
                log_to_database(session_id, "FFMPEG", f"Batch {batch_index}: {line.strip()}", video_path)
        process.wait()
        
        end_msg = f"✅ Batch {batch_index}: Streaming completed successfully"
        log_callback(end_msg)
        if session_id:
            log_to_database(session_id, "INFO", f"Batch {batch_index}: {end_msg}", video_path)
            
    except Exception as e:
        error_msg = f"❌ Batch {batch_index}: FFmpeg Error: {e}"
        log_callback(error_msg)
        if session_id:
            log_to_database(session_id, "ERROR", f"Batch {batch_index}: {error_msg}", video_path)
    finally:
        final_msg = f"⏹️ Batch {batch_index}: Streaming session ended"
        log_callback(final_msg)
        if session_id:
            log_to_database(session_id, "INFO", f"Batch {batch_index}: {final_msg}", video_path)

def auto_process_auth_code():
    """Process authorization tokens from URL - MANUAL REDIRECT ONLY"""
    # Check URL parameters
    query_params = st.query_params
    
    # Cek apakah sudah diproses sebelumnya
    if 'tokens_processed' not in st.session_state:
        st.session_state['tokens_processed'] = False
    
    if 'tokens' in query_params and not st.session_state['tokens_processed']:
        tokens_json = query_params['tokens']
        try:
            # Decode dan parse tokens
            decoded_tokens = urllib.parse.unquote(tokens_json)
            tokens = json.loads(decoded_tokens)
            st.session_state['youtube_tokens'] = tokens
            st.session_state['tokens_processed'] = True  # Tandai sudah diproses
            st.success("✅ Successfully connected to YouTube!")
            # Hapus parameter tokens dari URL
            st.query_params.clear()
        except Exception as e:
            st.error(f"❌ Failed to process token: {str(e)}")
            st.session_state['tokens_processed'] = True  # Tetap tandai sudah diproses

def get_youtube_categories():
    """Get YouTube video categories"""
    return {
        "1": "Film & Animation",
        "2": "Autos & Vehicles", 
        "10": "Music",
        "15": "Pets & Animals",
        "17": "Sports",
        "19": "Travel & Events",
        "20": "Gaming",
        "22": "People & Blogs",
        "23": "Comedy",
        "24": "Entertainment",
        "25": "News & Politics",
        "26": "Howto & Style",
        "27": "Education",
        "28": "Science & Technology"
    }

# Fungsi untuk auto start streaming
def auto_start_streaming(video_path, stream_key, is_shorts=False, custom_rtmp=None, session_id=None, duration_limit=None, video_settings=None, batch_index=0):
    """Auto start streaming dengan konfigurasi default"""
    if not video_path or not stream_key:
        st.error("❌ Video atau stream key tidak ditemukan!")
        return False
    
    # Set session state untuk streaming
    if 'batch_streams' not in st.session_state:
        st.session_state['batch_streams'] = {}
    
    batch_key = f"batch_{batch_index}"
    st.session_state['batch_streams'][batch_key] = {
        'streaming': True,
        'stream_start_time': datetime.now(),
        'live_logs': []
    }
    
    def log_callback(msg):
        if 'batch_streams' not in st.session_state:
            st.session_state['batch_streams'] = {}
        if batch_key not in st.session_state['batch_streams']:
            st.session_state['batch_streams'][batch_key] = {'live_logs': []}
        if 'live_logs' not in st.session_state['batch_streams'][batch_key]:
            st.session_state['batch_streams'][batch_key]['live_logs'] = []
            
        st.session_state['batch_streams'][batch_key]['live_logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        # Keep only last 100 logs in memory
        if len(st.session_state['batch_streams'][batch_key]['live_logs']) > 100:
            st.session_state['batch_streams'][batch_key]['live_logs'] = st.session_state['batch_streams'][batch_key]['live_logs'][-100:]
    
    # Jalankan FFmpeg di thread terpisah
    ffmpeg_thread = threading.Thread(
        target=run_ffmpeg, 
        args=(video_path, stream_key, is_shorts, log_callback, custom_rtmp or None, session_id, duration_limit, video_settings, batch_index), 
        daemon=True
    )
    ffmpeg_thread.start()
    
    # Simpan referensi thread
    if 'ffmpeg_threads' not in st.session_state:
        st.session_state['ffmpeg_threads'] = {}
    st.session_state['ffmpeg_threads'][batch_key] = ffmpeg_thread
    
    # Log ke database
    log_to_database(session_id, "INFO", f"Batch {batch_index}: Auto streaming started: {video_path}")
    return True

# Fungsi untuk auto create live broadcast dengan setting manual/otomatis
def auto_create_live_broadcast(service, use_custom_settings=True, custom_settings=None, session_id=None, batch_index=0):
    """Auto create live broadcast dengan setting manual atau otomatis"""
    try:
        with st.spinner(f"Creating auto YouTube Live broadcast for batch {batch_index}..."):
            # Schedule for immediate start
            scheduled_time = datetime.now() + timedelta(seconds=30)
            
            # Default settings
            default_settings = {
                'title': f"Live Stream - Batch {batch_index}",
                'description': f"Live streaming session - Batch {batch_index}",
                'tags': [],
                'category_id': "20",  # Gaming
                'privacy_status': "public",
                'made_for_kids': False
            }
            
            # Gunakan setting custom jika tersedia
            if use_custom_settings and custom_settings:
                settings = custom_settings
            else:
                settings = default_settings
            
            live_info = create_live_stream(
                service, 
                settings['title'],
                settings['description'],
                scheduled_time,
                settings['tags'],
                settings['category_id'],
                settings['privacy_status'],
                settings['made_for_kids']
            )
            
            if live_info:
                if 'batch_live_info' not in st.session_state:
                    st.session_state['batch_live_info'] = {}
                st.session_state['batch_live_info'][f"batch_{batch_index}"] = live_info
                st.success(f"🎉 Batch {batch_index}: Auto YouTube Live Broadcast Created Successfully!")
                log_to_database(session_id, "INFO", f"Batch {batch_index}: Auto YouTube Live created: {live_info['watch_url']}")
                return live_info
            else:
                st.error(f"❌ Batch {batch_index}: Failed to create auto live broadcast")
                return None
    except Exception as e:
        error_msg = f"Batch {batch_index}: Error creating auto YouTube Live: {e}"
        st.error(error_msg)
        log_to_database(session_id, "ERROR", error_msg)
        return None

def main():
    # Page configuration must be the first Streamlit command
    st.set_page_config(
        page_title="Advanced YouTube Live Streaming",
        page_icon="📺",
        layout="wide"
    )
    
    # Initialize database
    init_database()
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if 'live_logs' not in st.session_state:
        st.session_state['live_logs'] = []
    
    st.title("🎥 Advanced YouTube Live Streaming Platform")
    st.markdown("---")
    
    # Auto-process authorization code if present
    auto_process_auth_code()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("📋 Configuration")
        
        # Session info
        st.info(f"🆔 Session: {st.session_state['session_id']}")
        
        # Saved Channels Section
        st.subheader("💾 Saved Channels")
        saved_channels = load_saved_channels()
        
        if saved_channels:
            st.write("**Previously authenticated channels:**")
            for channel in saved_channels:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📺 {channel['name']}")
                    st.caption(f"Last used: {channel['last_used'][:10]}")
                
                with col2:
                    if st.button("🔑 Use", key=f"use_{channel['name']}"):
                        # Load this channel's authentication
                        service = create_youtube_service(channel['auth'])
                        if service:
                            # Verify the authentication is still valid
                            channels = get_channel_info(service)
                            if channels:
                                channel_info = channels[0]
                                st.session_state['youtube_service'] = service
                                st.session_state['channel_info'] = channel_info
                                update_channel_last_used(channel['name'])
                                st.success(f"✅ Loaded: {channel['name']}")
                                st.rerun()
                            else:
                                st.error("❌ Authentication expired")
                        else:
                            st.error("❌ Failed to load authentication")
        else:
            st.info("No saved channels. Authenticate below to save.")
        
        # Google OAuth Configuration
        st.subheader("🔐 Google OAuth Setup")
        
        # Predefined Auth Button
        st.markdown("### 🚀 Quick Auth (Predefined)")
        if st.button("🔑 Use Predefined OAuth Config", help="Use built-in OAuth configuration"):
            st.session_state['oauth_config'] = PREDEFINED_OAUTH_CONFIG['web']
            st.success("✅ Predefined OAuth config loaded!")
            st.rerun()
        
        # Authorization Process
        if 'oauth_config' in st.session_state:
            oauth_config = st.session_state['oauth_config']
            
            # Generate authorization URL with state parameter
            st.markdown("### 🔗 Authorization Link")
            
            # Dapatkan URL aplikasi saat ini
            try:
                import os
                host = os.environ.get('HOST', '')
                if host:
                    current_app_url = f"https://{host}"
                else:
                    current_app_url = f"https://{st.context.headers.get('Host', '')}" if hasattr(st, 'context') and hasattr(st.context, 'headers') else ''
            except:
                current_app_url = ''
            
            # Fallback: input manual
            if not current_app_url:
                user_url = st.text_input("Enter your app URL", 
                                       placeholder="yourapp.streamlit.app",
                                       key="manual_app_url_input")
                if user_url:
                    user_url = user_url.replace('https://', '').replace('http://', '').split('/')[0]
                    current_app_url = f"https://{user_url}"
                    st.session_state['manual_app_url'] = current_app_url
            
            # Gunakan URL manual jika tersedia
            if 'manual_app_url' in st.session_state:
                current_app_url = st.session_state['manual_app_url']
            
            if current_app_url:
                # Bersihkan URL
                clean_host = current_app_url.replace('https://', '').replace('http://', '').split('/')[0]
                current_app_url = f"https://{clean_host}"
