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

def auto_process_auth_code():
    """Process authorization tokens from URL - MANUAL REDIRECT ONLY"""
    # Check URL parameters
    query_params = st.query_params
    
    # Debug info
    st.write("Debug - Query params:", dict(query_params))
    
    # Cek apakah sudah diproses sebelumnya
    if 'tokens_processed' not in st.session_state:
        st.session_state['tokens_processed'] = False
    
    if 'tokens' in query_params and not st.session_state['tokens_processed']:
        tokens_json = query_params['tokens']
        st.write("Debug - Raw tokens:", tokens_json[:100] + "..." if len(tokens_json) > 100 else tokens_json)
        
        try:
            # Decode dan parse tokens
            decoded_tokens = urllib.parse.unquote(tokens_json)
            st.write("Debug - Decoded tokens:", decoded_tokens[:100] + "..." if len(decoded_tokens) > 100 else decoded_tokens)
            
            tokens = json.loads(decoded_tokens)
            st.session_state['youtube_tokens'] = tokens
            st.session_state['tokens_processed'] = True  # Tandai sudah diproses
            
            # Create YouTube service from tokens
            service = create_youtube_service(tokens)
            if service:
                st.session_state['youtube_service'] = service
                
                # Get channel info
                channels = get_channel_info(service)
                if channels:
                    channel = channels[0]
                    st.session_state['channel_info'] = channel
                    
                    # Save channel authentication persistently
                    save_channel_auth(
                        channel['snippet']['title'],
                        channel['id'],
                        tokens
                    )
                    
                    st.success(f"✅ Successfully connected to YouTube channel: {channel['snippet']['title']}!")
                else:
                    st.warning("Connected to YouTube but couldn't fetch channel info")
            else:
                st.error("❌ Failed to create YouTube service from tokens")
            
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
    
    # Debug section
    with st.expander("🔧 Debug Info"):
        st.write("Session State Keys:", list(st.session_state.keys()))
        if 'youtube_tokens' in st.session_state:
            st.write("✅ YouTube tokens available")
        if 'youtube_service' in st.session_state:
            st.write("✅ YouTube service created")
        if 'channel_info' in st.session_state:
            st.write("✅ Channel info loaded")
            st.json(st.session_state['channel_info']['snippet'])
    
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
                
                # Generate auth URL dengan state parameter
                auth_url = generate_auth_url_with_state(oauth_config, current_app_url)
                if auth_url:
                    st.markdown(f"[Click here to authorize]({auth_url})")
                    st.info("ℹ️ After authorization, you'll need to click a button to return to this app")
                    
                    # Instructions
                    with st.expander("💡 Instructions"):
                        st.write("1. Click the authorization link above")
                        st.write("2. Grant permissions to your YouTube account")
                        st.write("3. You'll be redirected to auth handler")
                        st.write("4. Click 'Go Back to My App' button")
                        st.write("5. You'll be returned here with authentication")
                else:
                    st.error("Failed to generate authorization URL")
            else:
                st.warning("📝 Enter your app URL to generate authorization link")
        
        # Log Management
        st.markdown("---")
        st.subheader("📊 Log Management")
        
        col_log1, col_log2 = st.columns(2)
        with col_log1:
            if st.button("🔄 Refresh Logs"):
                st.rerun()
        
        with col_log2:
            if st.button("🗑️ Clear Session Logs"):
                st.session_state['live_logs'] = []
                st.success("Logs cleared!")
        
        # Export logs
        if st.button("📥 Export All Logs"):
            all_logs = get_logs_from_database(limit=1000)
            if all_logs:
                logs_text = "\n".join([f"[{log[0]}] {log[1]}: {log[2]}" for log in all_logs])
                st.download_button(
                    label="💾 Download Logs",
                    data=logs_text,
                    file_name=f"streaming_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎥 Video & Streaming Setup")
        
        # YouTube Authentication Status
        if 'youtube_service' in st.session_state and 'channel_info' in st.session_state:
            st.subheader("📺 YouTube Channel")
            channel = st.session_state['channel_info']
            col_ch1, col_ch2 = st.columns(2)
            
            with col_ch1:
                st.write(f"**Channel:** {channel['snippet']['title']}")
                st.write(f"**Subscribers:** {channel['statistics'].get('subscriberCount', 'Hidden')}")
            
            with col_ch2:
                st.write(f"**Views:** {channel['statistics'].get('viewCount', '0')}")
                st.write(f"**Videos:** {channel['statistics'].get('videoCount', '0')}")
                
            st.success("✅ YouTube authentication successful!")
        else:
            st.info("🔐 Please authenticate with YouTube using the sidebar")

if __name__ == '__main__':
    main()
