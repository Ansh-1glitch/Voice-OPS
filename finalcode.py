import streamlit as st
import os, shutil, threading, hashlib, re, difflib
from datetime import datetime
from string import ascii_uppercase
from send2trash import send2trash
import time
import concurrent.futures

#for text to voice 
import pyttsx3

# to recognize voice
import speech_recognition as sr

st.set_page_config(
    page_title="Echo File Assistant Pro",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# UI of streamlit 
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 800;
        letter-spacing: -1px;
    }
    
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 3rem;
        font-weight: 400;
    }
    
    .operation-card {
        background: #ffffff;
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #f0f0f0;
        margin-bottom: 2rem;
        transition: all 0.3s ease;
    }
    
    .operation-card:hover {
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    .stButton button {
        height: 48px;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
        border: none;
    }
    
    .stButton button:hover {
        transform: scale(1.02);
    }
    
    /* Custom Selectbox Styling */
    div[data-baseweb="select"] > div {
        border-radius: 10px;
        border-color: #e0e0e0;
    }
    
    /* Input Field Styling */
    .stTextInput input {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        padding: 10px 15px;
    }
    
    .stTextInput input:focus {
        border-color: #4b6cb7;
        box-shadow: 0 0 0 2px rgba(75, 108, 183, 0.2);
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
    
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #182848;
        margin-bottom: 1rem;
    }
    
    .voice-log {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        background: #2d3436;
        color: #00cec9;
        padding: 10px;
        border-radius: 8px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# voice part 
@st.cache_resource
def get_voice_engine():
    """Cached voice engine for better performance"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 160) 
        engine.setProperty('volume', 1.0)
        
        voices = engine.getProperty('voices')
        for voice in voices:
            if "en-us" in voice.id.lower() or "english" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        return engine
    except Exception:
        return None

def speak(text: str):
    """Enhanced TTS with better error handling"""
    try:
        engine = get_voice_engine()
        if engine:
            engine.say(text)
            engine.runAndWait()
    except Exception:
        pass 

def listen_once(timeout=5, phrase_time_limit=8):
    """Enhanced speech recognition with better feedback"""
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        status_container = st.empty()
        status_container.info("🎤 Listening... Speak now!")
        
        try:
            audio = recognizer.listen(
                source, 
                timeout=timeout, 
                phrase_time_limit=phrase_time_limit
            )
            status_container.info("🔄 Processing speech...")
            
            text = recognizer.recognize_google(audio, language="en-IN")
            status_container.empty()
            return text.strip()
                
        except sr.WaitTimeoutError:
            status_container.warning("⏰ Listening timeout.")
            time.sleep(1)
            status_container.empty()
            return None
        except sr.UnknownValueError:
            status_container.warning("❌ Could not understand audio.")
            time.sleep(1)
            status_container.empty()
            return None
        except Exception as e:
            status_container.error(f"🎤 Error: {e}")
            time.sleep(1)
            status_container.empty()
            return None

# file operations 
def get_full_path(folder_name: str):
    """Enhanced path resolution with better validation - CASE INSENSITIVE"""
    if not folder_name:
        return None
    
    home = os.path.expanduser("~")
    folder_map = {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "videos": os.path.join(home, "Videos"),
        "music": os.path.join(home, "Music"),
    }
    
    key = folder_name.strip().lower()
    if key in folder_map:
        return folder_map[key]
    if os.path.isabs(folder_name):
        return folder_name
    
    guess = os.path.join(home, folder_name)
    return guess if os.path.exists(guess) else None

def find_file_deep(filename: str, max_results=1):
    """Robust deep search across all available drives with fuzzy matching fallback."""
    if not filename:
        return []
    
    drives = [f"{d}:\\" for d in ascii_uppercase if os.path.exists(f"{d}:\\")]
    found_files = []
    target_lower = filename.lower()
    
    home = os.path.expanduser("~")
    priority_dirs = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Music"),
        os.path.join(home, "Videos")
    ]

    # fast searching ke liye
    for p_dir in priority_dirs:
        if os.path.exists(p_dir):
            for root, dirs, files in os.walk(p_dir):
                for file in files:
                    if file.lower() == target_lower:
                        found_files.append(os.path.join(root, file))
                        if len(found_files) >= max_results:
                            return found_files

    if found_files:
        return found_files

    # deep search file na find hone pr
    def search_drive_recursive(drive_path):
        drive_matches = []
        try:
            for root, dirs, files in os.walk(drive_path):
                if 'Windows' in root or 'Program Files' in root or 'AppData' in root:
                    continue
                for file in files:
                    if file.lower() == target_lower:
                        drive_matches.append(os.path.join(root, file))
                        if len(drive_matches) >= max_results:
                            return drive_matches
        except Exception:
            pass
        return drive_matches

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_drive = {executor.submit(search_drive_recursive, drive): drive for drive in drives}
        for future in concurrent.futures.as_completed(future_to_drive):
            results = future.result()
            found_files.extend(results)
            if len(found_files) >= max_results:
                break
                
    if found_files:
        return found_files

    best_match = None
    highest_ratio = 0.0
    cutoff = 0.6

    for p_dir in priority_dirs:
        if os.path.exists(p_dir):
            for root, dirs, files in os.walk(p_dir):
                for file in files:
                    # lowercase cover krne ke liye
                    ratio = difflib.SequenceMatcher(None, target_lower, file.lower()).ratio()
                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = os.path.join(root, file)
    
    if best_match and highest_ratio >= cutoff:
        return [best_match]
                
    return found_files

def ensure_writable_folder(path):
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return os.access(path, os.W_OK), "Folder is writable"
    except Exception as e:
        return False, str(e)

def op_upload(filename, dest_folder):
    if not filename:
        return False, "No filename provided"
    
    with st.spinner(f"🔍 Deep searching for '{filename}'..."):
        file_paths = find_file_deep(filename)
    
    if not file_paths:
        return False, f"File '{filename}' not found on system"
    
    dest_path = get_full_path(dest_folder)
    if not dest_path:
        return False, f"Destination folder '{dest_folder}' not found"
    
    writable, message = ensure_writable_folder(dest_path)
    if not writable:
        return False, f"Cannot write to destination: {message}"
    
    try:
        source_path = file_paths[0]
        destination = os.path.join(dest_path, os.path.basename(source_path))
        shutil.move(source_path, destination)
        return True, f"✅ Successfully moved '{filename}' to {dest_folder}"
    except Exception as e:
        return False, f"Upload failed: {str(e)}"

def op_rename(old_name, new_name):
    if not old_name or not new_name:
        return False, "Both old and new names are required"
    
    with st.spinner(f"🔍 Deep searching for '{old_name}'..."):
        file_paths = find_file_deep(old_name)
    
    if not file_paths:
        return False, f"File '{old_name}' not found"
    
    try:
        old_path = file_paths[0]
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        
        if os.path.exists(new_path):
            return False, f"A file with name '{new_name}' already exists in the same location"
        
        os.rename(old_path, new_path)
        return True, f"✅ Renamed '{old_name}' to '{new_name}'"
    except Exception as e:
        return False, f"Rename failed: {str(e)}"

def list_all_files(folder_path):
    files_data = []
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    files_data.append({
                        "Name": file,
                        "Path": file_path,
                        "Size (KB)": round(stat.st_size / 1024, 2),
                        "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "Type": os.path.splitext(file)[1] or "No extension"
                    })
                except Exception:
                    continue
    except Exception as e:
        st.error(f"Error reading folder: {e}")
    
    return files_data

def op_dedupe(folder_path):
    seen_hashes = {}
    duplicates_removed = []
    
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    
                    if file_hash in seen_hashes:
                        send2trash(file_path)
                        duplicates_removed.append(file_path)
                    else:
                        seen_hashes[file_hash] = file_path
                except Exception:
                    continue
    except Exception as e:
        st.error(f"Error during deduplication: {e}")
    
    return duplicates_removed

def get_storage_usage(folder_path):
    total_size = 0
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, file))
                except Exception:
                    continue
    except Exception:
        return 0
    
    return round(total_size / (1024 * 1024), 2)

def sort_files_by_date(folder_path, newest_first=True):
    files = list_all_files(folder_path)
    files.sort(
        key=lambda x: datetime.strptime(x["Modified"], "%Y-%m-%d %H:%M:%S"),
        reverse=newest_first
    )
    return files

# UI ka function

def input_with_mic(label, key, placeholder="", help_text=""):
    """
    Creates a text input field with a microphone button next to it.
    Handles the Streamlit widget state correctly to avoid warnings.
    """
    col1, col2 = st.columns([0.9, 0.1])
    
    if key not in st.session_state:
        st.session_state[key] = ""
        
    widget_key = f"{key}_input"
    
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state[key]

    # render button
    with col2:
        st.write("") 
        st.write("")
        if st.button("🎤", key=f"{key}_mic", help="Click to speak"):
            voice_text = listen_once()
            if voice_text:
                st.session_state[key] = voice_text
                st.session_state[widget_key] = voice_text
                st.session_state["last_voice_update"] = key
                st.rerun()

    with col1:
        text_val = st.text_input(
            label, 
            placeholder=placeholder,
            key=widget_key,
            help=help_text
        )
        
        if text_val != st.session_state[key]:
            st.session_state[key] = text_val
                
    return st.session_state[key]

# manual mode
def render_upload_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("📤 Upload File")
    
    col1, col2 = st.columns(2)
    
    with col1:
        filename = input_with_mic(
            "Filename to upload (with extension):", 
            key="upload_filename",
            placeholder="example.pdf, photo.jpg..."
        )
    
    with col2:
        destination = st.selectbox(
            "Destination folder:",
            ["Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music", "Custom"],
            key="upload_dest"
        )
        
        if destination == "Custom":
            custom_dest = input_with_mic("Custom folder path:", key="upload_custom")
            destination = custom_dest
    
    if st.session_state.get("last_voice_update") == "upload_filename" and filename:
        st.session_state["last_voice_update"] = None
        with st.spinner(f"🚀 Auto-starting upload for {filename}..."):
            success, message = op_upload(filename, destination)
            if success:
                st.success(message)
                speak("File uploaded successfully!")
            else:
                st.error(message)
                speak("Upload failed!")
    
    if st.button("🚀 Upload File", type="primary", use_container_width=True, key="upload_btn"):
        if not filename:
            st.error("Please enter a filename")
            return
        
        with st.spinner(f"Uploading {filename}..."):
            success, message = op_upload(filename, destination)
        
        if success:
            st.success(message)
            speak("File uploaded successfully!")
        else:
            st.error(message)
            speak("Upload failed!")
    st.markdown('</div>', unsafe_allow_html=True)

def render_delete_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("🗑️ Delete File")
    
    filename = input_with_mic(
        "Filename to delete:", 
        key="delete_filename",
        placeholder="Enter filename with extension"
    )
    
    if st.session_state.get("last_voice_update") == "delete_filename" and filename:
        st.session_state["last_voice_update"] = None
        with st.spinner("🔍 Deep searching for file..."):
            file_paths = find_file_deep(filename)
            if file_paths:
                st.session_state.delete_candidate = file_paths[0]
                st.success(f"Found: {file_paths[0]}")
                speak(f"Found {filename}. Please confirm deletion.")
            else:
                st.error("File not found")
                speak("File not found.")
                st.session_state.delete_candidate = None

    if st.button("🔍 Find File", use_container_width=True, key="find_delete"):
        if not filename:
            st.error("Please enter a filename")
            return
        
        with st.spinner("Searching for file..."):
            file_paths = find_file_deep(filename)
        
        if file_paths:
            st.session_state.delete_candidate = file_paths[0]
            st.success(f"Found: {file_paths[0]}")
            
            file_size = os.path.getsize(file_paths[0]) / (1024 * 1024)
            st.info(f"File size: {file_size:.2f} MB • Location: {os.path.dirname(file_paths[0])}")
        else:
            st.error("File not found")
            st.session_state.delete_candidate = None
    
    if st.session_state.get('delete_candidate'):
        st.warning(f"⚠️ File to delete: {st.session_state.delete_candidate}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Delete", type="primary", use_container_width=True, key="confirm_delete"):
                try:
                    file_size = os.path.getsize(st.session_state.delete_candidate) / (1024 * 1024)
                    send2trash(st.session_state.delete_candidate)
                    st.success(f"✅ Moved to Recycle Bin: {st.session_state.delete_candidate} (Size: {file_size:.2f} MB)")
                    speak("File moved to recycle bin successfully!")
                    st.session_state.delete_candidate = None
                except Exception as e:
                    st.error(f"Deletion failed: {e}")
        with col2:
            if st.button("❌ Cancel", use_container_width=True, key="cancel_delete"):
                st.session_state.delete_candidate = None
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def render_rename_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("📝 Rename File")
    
    col1, col2 = st.columns(2)
    
    with col1:
        old_name = input_with_mic(
            "Current filename:", 
            key="rename_old",
            placeholder="old_file.pdf",
            help_text="Enter the current filename with extension"
        )
        
        if st.session_state.get("last_voice_update") == "rename_old" and old_name:
            st.session_state["last_voice_update"] = None
            with st.spinner("🔍 Deep searching for file..."):
                file_paths = find_file_deep(old_name)
                if file_paths:
                    st.session_state.rename_old_path = file_paths[0]
                    st.success(f"Found: {file_paths[0]}")
                    speak("Found file. What is the new name?")
                else:
                    st.error("File not found")
                    speak("File not found.")
        
        if st.button("🔍 Find Current File", use_container_width=True, key="find_old"):
            if not old_name:
                st.error("Please enter current filename")
            else:
                with st.spinner("Searching for file..."):
                    file_paths = find_file_deep(old_name)
                if file_paths:
                    st.success(f"Found: {file_paths[0]}")
                    st.session_state.rename_old_path = file_paths[0]
                else:
                    st.error("File not found")
                    st.session_state.rename_old_path = None
    
    with col2:
        new_name = input_with_mic(
            "New filename:", 
            key="rename_new",
            placeholder="new_file.pdf",
            help_text="Enter the new filename with extension"
        )
        
        # rename
        if st.session_state.get("last_voice_update") == "rename_new" and new_name and st.session_state.get('rename_old_path'):
             st.session_state["last_voice_update"] = None
             with st.spinner("🔄 Auto-renaming file..."):
                success, message = op_rename(old_name, new_name)
                if success:
                    st.success(message)
                    speak("File renamed successfully!")
                    st.session_state.rename_old_path = None
                else:
                    st.error(message)
                    speak("Rename failed!")

    if st.session_state.get('rename_old_path'):
        st.info(f"Current file location: {st.session_state.rename_old_path}")
    
    if st.button("🔄 Rename File", type="primary", use_container_width=True, key="rename_btn"):
        if not old_name:
            st.error("Please enter current filename")
            return
        if not new_name:
            st.error("Please enter new filename")
            return
        
        with st.spinner("Renaming file..."):
            success, message = op_rename(old_name, new_name)
        
        if success:
            st.success(message)
            speak("File renamed successfully!")
            st.session_state.rename_old_path = None
        else:
            st.error(message)
            speak("Rename failed!")
    st.markdown('</div>', unsafe_allow_html=True)

def render_show_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("📋 Show Files in Folder")
    
    folder = st.selectbox(
        "Select folder:",
        ["Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music", "Custom"],
        key="show_folder"
    )
    
    if folder == "Custom":
        custom_folder = input_with_mic("Custom folder path:", key="show_custom")
        folder = custom_folder
        
        if st.session_state.get("last_voice_update") == "show_custom" and custom_folder:
            st.session_state["last_voice_update"] = None
            folder_path = get_full_path(custom_folder)
            if folder_path and os.path.exists(folder_path):
                with st.spinner("Scanning folder..."):
                    files = list_all_files(folder_path)
                    if files:
                        st.success(f"Found {len(files)} files")
                        st.dataframe(files, use_container_width=True)
                        speak(f"Found {len(files)} files.")
                        return
    
    if st.session_state.get("auto_trigger_show") and folder:
        st.session_state["auto_trigger_show"] = False # Reset
        folder_path = get_full_path(folder)
        if folder_path and os.path.exists(folder_path):
             with st.spinner("Scanning folder..."):
                files = list_all_files(folder_path)
                if files:
                    st.success(f"Found {len(files)} files")
                    st.dataframe(files, use_container_width=True)
                    speak(f"Found {len(files)} files in {folder}.")
                    return

    if st.button("📁 List Files", type="primary", use_container_width=True, key="show_btn"):
        folder_path = get_full_path(folder)
        
        if not folder_path or not os.path.exists(folder_path):
            st.error("Invalid folder path")
            return
        
        with st.spinner("Scanning folder..."):
            files = list_all_files(folder_path)
        
        if files:
            st.success(f"Found {len(files)} files")
            st.dataframe(files, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Files", len(files))
            with col2:
                total_size = sum(f["Size (KB)"] for f in files) / 1024
                st.metric("Total Size", f"{total_size:.1f} MB")
            with col3:
                extensions = len(set(f["Type"] for f in files))
                st.metric("File Types", extensions)
        else:
            st.info("No files found in the specified folder")
    st.markdown('</div>', unsafe_allow_html=True)

def render_storage_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("💾 Check Storage Usage")
    
    folder = st.selectbox(
        "Select folder:",
        ["Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music", "Custom"],
        key="storage_folder"
    )
    
    if folder == "Custom":
        custom_folder = input_with_mic("Custom folder path:", key="storage_custom")
        folder = custom_folder
        
        if st.session_state.get("last_voice_update") == "storage_custom" and custom_folder:
            st.session_state["last_voice_update"] = None
            folder_path = get_full_path(custom_folder)
            if folder_path and os.path.exists(folder_path):
                with st.spinner("Calculating storage..."):
                    storage_mb = get_storage_usage(folder_path)
                st.success(f"📊 Storage Usage: {storage_mb} MB")
                speak(f"Storage used is {storage_mb} megabytes")
                return
    
    if st.session_state.get("auto_trigger_storage") and folder:
        st.session_state["auto_trigger_storage"] = False # Reset
        folder_path = get_full_path(folder)
        if folder_path and os.path.exists(folder_path):
            with st.spinner("Calculating storage..."):
                storage_mb = get_storage_usage(folder_path)
            st.success(f"📊 Storage Usage: {storage_mb} MB")
            speak(f"Storage used in {folder} is {storage_mb} megabytes")
            return

    if st.button("📊 Check Storage", type="primary", use_container_width=True, key="storage_btn"):
        folder_path = get_full_path(folder)
        
        if not folder_path or not os.path.exists(folder_path):
            st.error("Invalid folder path")
            return
        
        with st.spinner("Calculating storage..."):
            storage_mb = get_storage_usage(folder_path)
        
        st.success(f"📊 Storage Usage: {storage_mb} MB")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Folder", folder)
        with col2:
            st.metric("Storage Used", f"{storage_mb} MB")
        
        speak(f"Storage used in {folder} is {storage_mb} megabytes")
    st.markdown('</div>', unsafe_allow_html=True)

def render_sort_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("📅 Sort Files by Date")
    
    col1, col2 = st.columns(2)
    
    with col1:
        folder = st.selectbox(
            "Select folder:",
            ["Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music", "Custom"],
            key="sort_folder"
        )
        
        if folder == "Custom":
            custom_folder = input_with_mic("Custom folder path:", key="sort_custom")
            folder = custom_folder
            
            if st.session_state.get("last_voice_update") == "sort_custom" and custom_folder:
                st.session_state["last_voice_update"] = None
                folder_path = get_full_path(custom_folder)
                if folder_path and os.path.exists(folder_path):
                    with st.spinner("Sorting files..."):
                        files = sort_files_by_date(folder_path, newest_first=True)
                    if files:
                        st.success(f"Sorted {len(files)} files")
                        st.dataframe(files, use_container_width=True)
                        speak(f"Sorted {len(files)} files.")
                        return
    
    with col2:
        sort_order = st.radio("Sort order:", ["Newest First", "Oldest First"], key="sort_order")
    
    if st.session_state.get("auto_trigger_sort") and folder:
        st.session_state["auto_trigger_sort"] = False # Reset
        folder_path = get_full_path(folder)
        if folder_path and os.path.exists(folder_path):
            with st.spinner("Sorting files..."):
                files = sort_files_by_date(folder_path, newest_first=(sort_order == "Newest First"))
            if files:
                st.success(f"Sorted {len(files)} files")
                st.dataframe(files, use_container_width=True)
                speak(f"Sorted {len(files)} files in {folder}.")
                return

    if st.button("🔃 Sort Files", type="primary", use_container_width=True, key="sort_btn"):
        folder_path = get_full_path(folder)
        
        if not folder_path or not os.path.exists(folder_path):
            st.error("Invalid folder path")
            return
        
        with st.spinner("Sorting files..."):
            files = sort_files_by_date(folder_path, newest_first=(sort_order == "Newest First"))
        
        if files:
            st.success(f"Sorted {len(files)} files")
            st.dataframe(files, use_container_width=True)
            
            if files:
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"📄 First: {files[0]['Name']}")
                with col2:
                    st.info(f"📄 Last: {files[-1]['Name']}")
            
            speak(f"Sorted {len(files)} files by date")
        else:
            st.info("No files found in the specified folder")
            speak("No files found to sort")
    st.markdown('</div>', unsafe_allow_html=True)

def render_dedupe_interface():
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("🧹 Clean Duplicate Files")
    
    folder = st.selectbox(
        "Select folder to clean:",
        ["Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music", "Custom"],
        key="dedupe_folder"
    )
    
    if folder == "Custom":
        custom_folder = input_with_mic("Custom folder path:", key="dedupe_custom")
        folder = custom_folder
        
        if st.session_state.get("last_voice_update") == "dedupe_custom" and custom_folder:
            st.session_state["last_voice_update"] = None
            folder_path = get_full_path(custom_folder)
            if folder_path and os.path.exists(folder_path):
                with st.spinner("Scanning for duplicates..."):
                    duplicates = op_dedupe(folder_path)
                if duplicates:
                    st.success(f"✅ Removed {len(duplicates)} duplicate files")
                    speak(f"Removed {len(duplicates)} duplicate files")
                else:
                    st.info("🎉 No duplicate files found!")
                    speak("No duplicate files found")
                return
    
    if st.session_state.get("auto_trigger_dedupe") and folder:
        st.session_state["auto_trigger_dedupe"] = False # Reset
        folder_path = get_full_path(folder)
        if folder_path and os.path.exists(folder_path):
            with st.spinner("Scanning for duplicates..."):
                duplicates = op_dedupe(folder_path)
            if duplicates:
                st.success(f"✅ Removed {len(duplicates)} duplicate files")
                speak(f"Removed {len(duplicates)} duplicate files in {folder}")
            else:
                st.info("🎉 No duplicate files found!")
                speak("No duplicate files found")
            return

    if st.button("🚿 Clean Duplicates", type="primary", use_container_width=True, key="dedupe_btn"):
        folder_path = get_full_path(folder)
        
        if not folder_path or not os.path.exists(folder_path):
            st.error("Invalid folder path")
            return
        
        with st.spinner("Scanning for duplicates..."):
            duplicates = op_dedupe(folder_path)
        
        if duplicates:
            st.success(f"✅ Removed {len(duplicates)} duplicate files")
            st.dataframe(duplicates, use_container_width=True)
            speak(f"Removed {len(duplicates)} duplicate files")
        else:
            st.info("🎉 No duplicate files found!")
            speak("No duplicate files found")
    st.markdown('</div>', unsafe_allow_html=True)

# global voice command 
def extract_folder_from_command(command):
    """Extracts folder name from command like 'in music' or 'in downloads'"""
    command_lower = command.lower()
    folders = ["downloads", "documents", "desktop", "pictures", "videos", "music"]
    
    for folder in folders:
        if f"in {folder}" in command_lower or f"from {folder}" in command_lower:
            return folder.capitalize()
    return None

def process_global_voice_command(command):
    command_lower = command.lower()
    folder_context = extract_folder_from_command(command)
    
    if "upload" in command_lower:
        st.session_state.manual_operation = "Upload File"
        match = re.search(r'upload\s+([a-zA-Z0-9_\-\s]+\.\w{2,4})', command_lower)
        if match:
            st.session_state.upload_filename = match.group(1)
            st.session_state.upload_filename_input = match.group(1)
            st.session_state["last_voice_update"] = "upload_filename"
        if folder_context:
            st.session_state.upload_dest = folder_context
            
    elif "delete" in command_lower or "remove" in command_lower:
        st.session_state.manual_operation = "Delete File"
        match = re.search(r'(delete|remove)\s+([a-zA-Z0-9_\-\s]+\.\w{2,4})', command_lower)
        if match:
            st.session_state.delete_filename = match.group(2)
            st.session_state.delete_filename_input = match.group(2)
            st.session_state["last_voice_update"] = "delete_filename"
            
    elif "rename" in command_lower:
        st.session_state.manual_operation = "Rename File"
        
    elif "show" in command_lower or "list" in command_lower:
        st.session_state.manual_operation = "Show Files"
        if folder_context:
            st.session_state.show_folder = folder_context
            st.session_state["auto_trigger_show"] = True
        
    elif "storage" in command_lower:
        st.session_state.manual_operation = "Check Storage"
        if folder_context:
            st.session_state.storage_folder = folder_context
            st.session_state["auto_trigger_storage"] = True
        
    elif "sort" in command_lower or "short" in command_lower:
        st.session_state.manual_operation = "Sort Files"
        if folder_context:
            st.session_state.sort_folder = folder_context
            st.session_state["auto_trigger_sort"] = True
        
    elif "duplicate" in command_lower or "dedupe" in command_lower:
        st.session_state.manual_operation = "Clean Duplicates"
        if folder_context:
            st.session_state.dedupe_folder = folder_context
            st.session_state["auto_trigger_dedupe"] = True
        
    return f"Switched to {st.session_state.manual_operation}"

# streamlit 
def main():
    st.markdown('<div class="main-header">🗂️ Echo File Assistant Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Your Intelligent Voice-Controlled File Manager</div>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown('<div class="sidebar-header">🎙️ Voice Command Center</div>', unsafe_allow_html=True)
        
        if st.button("🎤 Activate Global Voice", type="primary", use_container_width=True):
            command = listen_once()
            if command:
                st.markdown(f'<div class="voice-log">🗣️ "{command}"</div>', unsafe_allow_html=True)
                msg = process_global_voice_command(command)
                st.success(msg)
                time.sleep(1)
                st.rerun()
        
        st.info("Try saying: 'Show storage in Music' or 'Upload report.pdf to Documents'")
        
        st.markdown("---")
        st.markdown('<div class="sidebar-header">⚙️ Controls</div>', unsafe_allow_html=True)
        
        if st.button("🔄 Reset Session", key="reset_btn", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
        st.markdown("---")
        st.markdown("""
        <div style="font-size: 0.8rem; color: #888;">
        <b>Pro Tips:</b><br>
        • Speak clearly and naturally<br>
        • Use full filenames for best results<br>
        • Say "in [folder]" to target specific folders
        </div>
        """, unsafe_allow_html=True)
    
    if "manual_operation" not in st.session_state:
        st.session_state.manual_operation = "Upload File"

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        operation = st.selectbox(
            "Select Operation Mode",
            ["Upload File", "Delete File", "Rename File", "Show Files", 
             "Check Storage", "Sort Files", "Clean Duplicates"],
            key="manual_operation",
            label_visibility="collapsed"
        )
    
    st.write("") 
    
    if operation == "Upload File":
        render_upload_interface()
    elif operation == "Delete File":
        render_delete_interface()
    elif operation == "Rename File":
        render_rename_interface()
    elif operation == "Show Files":
        render_show_interface()
    elif operation == "Check Storage":
        render_storage_interface()
    elif operation == "Sort Files":
        render_sort_interface()
    elif operation == "Clean Duplicates":
        render_dedupe_interface()

if 'delete_candidate' not in st.session_state:
    st.session_state.delete_candidate = None

if 'rename_old_path' not in st.session_state:
    st.session_state.rename_old_path = None

if __name__ == "__main__":
    main()
