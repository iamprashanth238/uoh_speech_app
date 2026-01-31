from flask import Blueprint, render_template, request, jsonify, session
import os, uuid, json
from config import Config

from database import reset_old_in_progress_prompts, add_recording_metadata
from utils.s3_utils import S3Manager

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def index():
    return render_template("index.html")

@main_bp.route("/submit_user_info", methods=["POST"])
def submit_user_info():
    age = request.form.get("age")
    gender = request.form.get("gender")
    location = request.form.get("location")
    state = request.form.get("state")
    
    if not all([age, gender, location, state]):
        return jsonify({"success": False, "error": "All fields are required"}), 400
    
    session["user_info"] = {
        "age": int(age),
        "gender": gender,
        "location": location,
        "state": state
    }
    
    # Reset completed count for new user session
    session["completed"] = 0
    
    return jsonify({"success": True})

@main_bp.route("/submit", methods=["POST"])
def submit():
    audio = request.files.get("audio")
    text = request.form.get("text")
    prompt_id = request.form.get("prompt_id")

    uid = "UOH_" + uuid.uuid4().hex[:8]
    
    user_info = session.get("user_info", {})
    state = user_info.get("state", "")
    is_tribal = state in ["TS-Tribal", "AP-Tribal"]

    # Define upload directories
    if is_tribal:
        uploads_audio_dir = Config.TRIBAL_AUDIO_DIR
        uploads_transcription_dir = Config.TRIBAL_TRANSCRIPTION_DIR
    else:
        uploads_audio_dir = Config.UPLOAD_AUDIO_DIR
        uploads_transcription_dir = Config.UPLOAD_TRANSCRIPTION_DIR
    
    os.makedirs(uploads_audio_dir, exist_ok=True)
    os.makedirs(uploads_transcription_dir, exist_ok=True)


    try:
        # Save audio locally
        audio_path = f"{uploads_audio_dir}/{uid}.wav"
        audio.save(audio_path)

        # Save transcription locally
        text_path = f"{uploads_transcription_dir}/{uid}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)


    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

    # --- S3 Upload Deferral ---
    # Store details in session for batch upload later
    pending_uploads = session.get("pending_uploads", [])
    pending_uploads.append({
        "uid": uid,
        "audio_path": audio_path,
        "text_path": text_path,
        "prompt_id": prompt_id,
        "prompt_text": text, # Store the text submitted for backup
        "is_tribal": is_tribal,
        "user_info": user_info
    })
    session["pending_uploads"] = pending_uploads
    session.modified = True
    
    print(f"✅ Saved {uid} locally. Queued for S3 (Queue size: {len(pending_uploads)})")
    
    # -------------------------

    # Update prompt status: Only if it's a numeric ID (DB)
    # If it is an S3 key, we currently do not change its state (no 'move to used' implemented yet)
    # If it is an S3 key, we currently do not change its state (no 'move to used' implemented yet)
    # DB State update removed
    # if prompt_id and str(prompt_id).isdigit():
    #     mark_prompt_as_used(prompt_id)

    # Increment session completed count
    session['completed'] = session.get('completed', 0) + 1

    return jsonify({"status": "saved"})

@main_bp.route("/finalize_session", methods=["POST"])
def finalize_session():
    pending_uploads = session.get("pending_uploads", [])
    
    if not pending_uploads:
        return jsonify({"status": "no_uploads", "message": "No pending uploads found."})
        
    s3 = S3Manager()
    success_count = 0
    
    print(f"🚀 Starting batch upload for {len(pending_uploads)} items...")
    
    for item in pending_uploads:
        try:
            uid = item["uid"]
            is_tribal = item["is_tribal"]
            prompt_id = item["prompt_id"]
            user_info = item["user_info"]
            
            # Paths
            audio_path = item["audio_path"]
            text_path = item["text_path"]
            
            # prefixes
            if is_tribal:
                s3_audio_prefix = Config.S3_TRIBAL_AUDIO_PREFIX
                s3_transcription_prefix = Config.S3_TRIBAL_TRANSCRIPTION_PREFIX
            else:
                s3_audio_prefix = Config.S3_AUDIO_PREFIX
                s3_transcription_prefix = Config.S3_TRANSCRIPTION_PREFIX

            # 1. Upload Audio
            s3_audio_key = f"{s3_audio_prefix}{uid}.wav"
            if not s3.upload_file(audio_path, s3_audio_key):
                raise Exception(f"Failed to upload audio to {s3_audio_key}")

            # 2. Upload Transcription
            s3_text_key = f"{s3_transcription_prefix}{uid}.txt"
            if not s3.upload_file(text_path, s3_text_key):
                raise Exception(f"Failed to upload transcription to {s3_text_key}")

            # 3. Upload Original Prompt Text (Optional but recommended to check)
            prompt_text_content = None
            if "/" in str(prompt_id) or ".txt" in str(prompt_id):
                 # S3 key
                 prompt_text_content = s3.read_file(prompt_id)
            
            if prompt_text_content:
                if is_tribal:
                    s3_prompt_prefix = Config.S3_PROMPTS_TRIBAL_PREFIX
                    s3_prompt_used = Config.S3_PROMPTS_TRIBAL_USED
                else:
                    s3_prompt_prefix = Config.S3_PROMPTS_STANDARD_PREFIX
                    s3_prompt_used = Config.S3_PROMPTS_STANDARD_USED
                    
                s3_actual_prompt_key = f"{s3_prompt_prefix}{uid}_prompt.txt"
                s3.upload_string(prompt_text_content, s3_actual_prompt_key)
                
                # Move original prompt from Available(root) to used
                if "/" in str(prompt_id): 
                    filename = os.path.basename(prompt_id)
                    dest_key = s3_prompt_used + filename
                    s3.move_file(prompt_id, dest_key)

            # 4. Upload Metadata
            if user_info:
                metadata_json = json.dumps(user_info, ensure_ascii=False)
                
                # Save to Dedicated Metadata folder (for Admin Dashboard)
                s3_dedicated_meta_key = f"{Config.S3_METADATA_PREFIX}{uid}_metadata.json"
                if not s3.upload_string(metadata_json, s3_dedicated_meta_key):
                    print(f"⚠️ Warning: Failed to upload metadata for {uid} to {s3_dedicated_meta_key}, but proceeding as audio/text are saved.")
                
            # 5. Save to Local Database for persistence and Admin Dashboard
            add_recording_metadata(
                uid=uid,
                user_info=user_info,
                audio_path=f"audio/{'tribal' if is_tribal else 'standard'}/{uid}.wav",
                prompt_text=item.get("prompt_text", ""),
                is_tribal=is_tribal
            )

            success_count += 1
            
        except Exception as e:
            print(f"❌ Critical error uploading session item {item.get('uid')}: {e}")
            # We don't increment success_count here
            
    print(f"✅ Batch upload completed. Success: {success_count}/{len(pending_uploads)}")
    
    # Clear pending uploads
    session["pending_uploads"] = []
    session.modified = True
    
    return jsonify({"status": "success", "uploaded": success_count})

@main_bp.route("/api/prompt", methods=["GET"])
def api_get_prompt():
    completed = session.get('completed', 0)
    if completed >= 5:
        return jsonify({"done": True, "completed": completed})
    
    # --- DIRECT S3 MODE ---
    user_info = session.get("user_info", {})
    state = user_info.get("state", "")
    is_tribal = state in ["TS-Tribal", "AP-Tribal"]
    
    s3 = S3Manager()
    if is_tribal:
        prefix = Config.S3_PROMPTS_TRIBAL_PREFIX
    else:
        prefix = Config.S3_PROMPTS_STANDARD_PREFIX
        
    s3_key, text = s3.get_random_file_from_prefix(prefix)
    
    if s3_key is None or text is None:
        # No prompts available in S3
        from utils.email_utils import send_admin_alert
        
        prompt_type = "Tribal" if is_tribal else "Standard"
        subject = f"Urgent: No {prompt_type} Prompts Available"
        body = f"The user is trying to access {prompt_type} prompts, but the S3 folder '{prefix}' appears to be empty or contains no text files.\n\nPlease upload more prompts via the Admin Dashboard immediately."
        
        send_admin_alert(subject, body)
        
        # Return generic done, but with error flag so frontend can show "Sorry" message
        return jsonify({"done": True, "completed": completed, "error": "no_prompts"})
        
    # Return S3 key as ID
    return jsonify({"id": s3_key, "text": text.strip(), "completed": completed})


@main_bp.route("/new_session", methods=["POST"])
def new_session():
    # Session reset
    # No need to release prompts as we are not locking them anymore.
    
    # Reset any very old in_progress prompts (more than 5 minutes) when starting new session
    # Check both DBs to be safe
    reset_old_in_progress_prompts(Config.DB_PATH)
    reset_old_in_progress_prompts(Config.TRIBAL_DB_PATH)
    
    session.clear()
    return jsonify({"status": "reset"})
