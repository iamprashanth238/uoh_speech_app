from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, Response
import os, json, csv, io
from datetime import datetime
from functools import wraps
from config import Config
from database import add_new_prompt, get_prompt_stats, get_total_recordings_count, get_all_recordings
from utils.s3_utils import S3Manager

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    # If already logged in, go to dashboard
    if session.get("admin"):
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Check if credentials are set in config
        admin_user = Config.ADMIN_USERNAME
        admin_pass = Config.ADMIN_PASSWORD
        
        if not admin_user or not admin_pass:
            flash("Admin credentials not configured on server.")
            return render_template("admin_login.html")

        if username == admin_user and password == admin_pass:
            session["admin"] = True
            session.permanent = True # Make session last across browser restarts if configured
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Invalid credentials")
    
    return render_template("admin_login.html")


@admin_bp.route("/dashboard")
@login_required
def admin_dashboard():
    
    try:
        s3 = S3Manager()
        
        # 1. Audio Files (Standard + Tribal)
        std_audio = s3.count_files(Config.S3_AUDIO_PREFIX)
        tribal_audio = s3.count_files(Config.S3_TRIBAL_AUDIO_PREFIX)
        audio_count = std_audio + tribal_audio
        
        # 2. Transcription Files (Standard + Tribal)
        std_trans = s3.count_files(Config.S3_TRANSCRIPTION_PREFIX)
        tribal_trans = s3.count_files(Config.S3_TRIBAL_TRANSCRIPTION_PREFIX)
        transcription_count = std_trans + tribal_trans
        
        # 3. Standard Prompts
        # Total in "prompts/standard/" includes subfolders like "used/"
        total_std = s3.count_files(Config.S3_PROMPTS_STANDARD_PREFIX)
        used_std = s3.count_files(Config.S3_PROMPTS_STANDARD_USED)
        # Available = Total - Used (Assuming no other significant subfolders)
        unused_std = max(0, total_std - used_std)
        
        prompt_stats = {
            'used': used_std,
            'unused': unused_std,
            'in_progress': 0 # Removed feature
        }
        
        # 4. Tribal Prompts
        total_tribal = s3.count_files(Config.S3_PROMPTS_TRIBAL_PREFIX)
        used_tribal = s3.count_files(Config.S3_PROMPTS_TRIBAL_USED)
        unused_tribal = max(0, total_tribal - used_tribal)
        
        tribal_prompt_stats = {
            'used': used_tribal,
            'unused': unused_tribal
        }
        
        # 5. Metadata / User Records (Now from Database for reliability, but fallback to S3 for Vercel)
        metadata_count = get_total_recordings_count()
        if metadata_count == 0:
             # Fallback: Count files in the dedicated metadata folder in S3
             metadata_count = s3.count_files(Config.S3_METADATA_PREFIX)
             # Note: CSV exports might exist in this folder too, so this is an estimate
             # but better than showing 0 when data exists.
        
        print(f"DEBUG DASHBOARD: Audio={audio_count}, Trans={transcription_count}, StdPrompts={prompt_stats}, Tribal={tribal_prompt_stats}, Metadata={metadata_count}")
        
    except Exception as e:
        print(f"Error fetching S3 stats in dashboard: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to zeros or local if S3 fails
        audio_count = 0
        transcription_count = 0
        prompt_stats = {'used': 0, 'unused': 0, 'in_progress': 0}
        tribal_prompt_stats = {'used': 0, 'unused': 0}
        metadata_count = 0
    
    return render_template("admin_dashboard.html", 
                         audio_count=audio_count,
                         transcription_count=transcription_count,
                         prompt_stats=prompt_stats,
                         tribal_prompt_stats=tribal_prompt_stats,
                         metadata_count=metadata_count)

@admin_bp.route("/metadata")
@login_required
def admin_metadata():
    
    # Get recordings from database
    recordings = get_all_recordings()
    metadata_count = len(recordings)
    
    return render_template("admin_metadata.html", 
                         metadata_count=metadata_count,
                         recordings=recordings)

@admin_bp.route("/metadata/download")
@login_required
def download_metadata():
    
    # Get metadata from database
    metadata_list = get_all_recordings()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['UID', 'Age', 'Gender', 'Location', 'State'])
    
    # Write data
    for meta in metadata_list:
        writer.writerow([
            meta.get('uid', ''),
            meta.get('age', ''),
            meta.get('gender', ''),
            meta.get('location', ''),
            meta.get('state', '')
        ])
    
    # Create response
    output.seek(0)
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=user_metadata_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )
    
    return response

@admin_bp.route("/add_prompt", methods=["POST"])
@login_required
def add_prompt():
    
    language = request.form.get("language", "te")
    text = request.form.get("text", "").strip()
    english_text = request.form.get("english_text", "").strip()
    db_type = request.form.get("db_type", "standard")
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        # Generate a unique ID (S3-only mode)
        import uuid
        prompt_uid = uuid.uuid4().hex[:8]
        
        if db_type == 'tribal':
            prompt_prefix = Config.S3_PROMPTS_TRIBAL_PREFIX
            en_prompt_prefix = Config.S3_PROMPTS_TRIBAL_ENGLISH_PREFIX
        else:
            prompt_prefix = Config.S3_PROMPTS_STANDARD_PREFIX
            en_prompt_prefix = Config.S3_PROMPTS_STANDARD_ENGLISH_PREFIX
            
        s3 = S3Manager()
        
        # 1. Upload Telugu prompt
        filename = f"UOH_{prompt_uid}.txt"
        s3_key = f"{prompt_prefix}{filename}"
        s3.upload_string(text, s3_key)
        
        # 2. Upload English transliteration (if provided)
        if english_text:
            s3_en_key = f"{en_prompt_prefix}{filename}"
            s3.upload_string(english_text, s3_en_key)
            
        return jsonify({"success": True, "message": f"Prompt added to S3 ({db_type}) as {filename}"})
             
    except Exception as e:
        print(f"Error adding prompt: {e}")
        return jsonify({"error": str(e)}), 500

def extract_and_upload_individual_files(added_prompts, prompt_prefix):
    """
    Helper function to upload individual text files to S3.
    added_prompts: List of (id, text) tuples
    prompt_prefix: S3 folder prefix
    """
    s3 = S3Manager()
    success_count = 0
    print(f"Starting S3 upload for {len(added_prompts)} prompts to {prompt_prefix}...")
    
    for pid, ptext in added_prompts:
        if pid:
            try:
                # Filename: UOH_{id}.txt
                s3_key = f"{prompt_prefix}UOH_{pid}.txt"
                if s3.upload_string(ptext, s3_key):
                    print(f"Uploaded: {s3_key}")
                    success_count += 1
                else:
                    print(f"Failed to upload: {s3_key}")
            except Exception as e:
                print(f"Error uploading {pid}: {e}")
                
    print(f"Completed S3 upload. Success: {success_count}/{len(added_prompts)}")
    return success_count

@admin_bp.route("/upload_prompts", methods=["POST"])
@login_required
def upload_prompts():

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.lower().endswith(('.csv', '.xlsx')):
        return jsonify({"error": "Only CSV or XLSX files are allowed"}), 400

    try:
        import csv, io, os, re, tempfile, shutil
        import pandas as pd

        file_content = file.read()
        default_language = request.form.get("language", "te")
        db_type = request.form.get("db_type", "tribal")

        if db_type == 'tribal':
            S3_PROMPT_PREFIX = Config.S3_PROMPTS_TRIBAL_PREFIX
            S3_EN_PROMPT_PREFIX = Config.S3_PROMPTS_TRIBAL_ENGLISH_PREFIX
        else:
            S3_PROMPT_PREFIX = Config.S3_PROMPTS_STANDARD_PREFIX
            S3_EN_PROMPT_PREFIX = Config.S3_PROMPTS_STANDARD_ENGLISH_PREFIX

        prompts_to_add = []
        txt_files = []


        def safe_filename(name: str) -> str:
            return re.sub(r"[^\w\-_.]", "_", name)

        # 🔹 temp directory (SAFE for cloud)
        temp_dir = tempfile.mkdtemp()

        # ================= CSV =================
        if file.filename.lower().endswith(".csv"):
            decoded = file_content.decode("utf-8", errors="ignore")
            stream = io.StringIO(decoded)
            reader = csv.DictReader(stream)

            if not reader.fieldnames:
                return jsonify({"error": "CSV has no headers"}), 400

            field_map = {h.lower(): h for h in reader.fieldnames}
            if "text" not in field_map:
                return jsonify({"error": "CSV must contain a 'text' column"}), 400

            text_col = field_map["text"]
            en_text_col = field_map.get("english-text") # From user requirement
            lang_col = field_map.get("language")
            id_col = field_map.get("prompt_id")

            for idx, row in enumerate(reader, start=1):
                text = (row.get(text_col) or "").strip()
                if not text:
                    continue
                
                en_text = (row.get(en_text_col) if en_text_col else "").strip()
                language = (row.get(lang_col) if lang_col else None) or default_language
                prompt_id = row.get(id_col) if id_col else f"UOH_{uuid.uuid4().hex[:6]}"

                # Save Telugu
                filename = safe_filename(f"{prompt_id}.txt")
                te_path = os.path.join(temp_dir, filename)
                with open(te_path, "w", encoding="utf-8") as f:
                    f.write(text)
                txt_files.append((te_path, S3_PROMPT_PREFIX))

                # Save English if exists
                if en_text:
                    en_path = os.path.join(temp_dir, f"en_{filename}")
                    with open(en_path, "w", encoding="utf-8") as f:
                        f.write(en_text)
                    txt_files.append((en_path, S3_EN_PROMPT_PREFIX, filename)) # Store original filename for S3 key

        # ================= XLSX =================
        else:
            df = pd.read_excel(io.BytesIO(file_content))

            cols = {str(c).lower(): c for c in df.columns}
            if "text" not in cols:
                return jsonify({"error": "Excel file must contain a 'text' column"}), 400

            text_col = cols["text"]
            en_text_col = cols.get("english-text")
            lang_col = cols.get("language")
            id_col = cols.get("prompt_id")

            for idx, row in df.iterrows():
                text = str(row[text_col]).strip()
                if not text or text.lower() == "nan":
                    continue

                en_text = (str(row[en_text_col]).strip() if en_text_col and pd.notna(row[en_text_col]) else "")
                language = (row[lang_col] if lang_col else None) or default_language
                prompt_id = row[id_col] if id_col else f"UOH_{uuid.uuid4().hex[:6]}"

                # Save Telugu
                filename = safe_filename(f"{prompt_id}.txt")
                te_path = os.path.join(temp_dir, filename)
                with open(te_path, "w", encoding="utf-8") as f:
                    f.write(text)
                txt_files.append((te_path, S3_PROMPT_PREFIX))

                # Save English if exists
                if en_text:
                    en_path = os.path.join(temp_dir, f"en_{filename}")
                    with open(en_path, "w", encoding="utf-8") as f:
                        f.write(en_text)
                    txt_files.append((en_path, S3_EN_PROMPT_PREFIX, filename))

        # ---------- S3 UPLOAD ONLY ----------
        # Removing DB dependency
        
        s3 = S3Manager()
        success_count = 0
        
        print(f"Starting bulk S3 upload for {len(prompts_to_add)} prompts...")
        
        for prompt_lang, prompt_text in prompts_to_add:
            try:
                # Generate reliable ID if needed, but usually we use the content hash or random UUID 
                # to avoid duplicates? Or just UUID.
                # Let's use the file generation we already did in 'txt_files' if possible?
                # Actually, the previous code generated temp files in 'txt_files'. We can use those!
                pass
            except:
                pass

        # Better approach: Iterate over the txt_files we already created in temp_dir
        # They are named "{prompt_id}_{language}.txt" (safe filename).
        # We need to make sure they match the "UOH_" convention or the simple text file convention expected by S3.
        # The previous 'add_prompt' used "UOH_{uuid}.txt".
        # Let's stick to the generated filenames or standardize them.
        # If the user provided IDs in CSV, we want to respect them.
        
        for item in txt_files:
            try:
                if len(item) == 2: # (local_path, s3_prefix) -> Telugu
                    path, prefix = item
                    filename = os.path.basename(path)
                else: # (local_path, s3_prefix, original_filename) -> English
                    path, prefix, filename = item
                
                s3_key = f"{prefix}{filename}"
                if s3.upload_file(path, s3_key):
                    success_count += 1
            except Exception as e:
                print(f"Failed to upload {item[0]}: {e}")

        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "success": True,
            "message": f"Uploaded {success_count} prompts directly to S3.",
            "txt_uploaded": success_count
        })

    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500



@admin_bp.route("/s3_status")
@login_required
def s3_status():
    
    try:
        s3 = S3Manager()
        
        # Local counts (reusing logic from dashboard but simplified)
        stats = {
            "Audio Queries": {
                "local": len([f for f in os.listdir(Config.UPLOAD_AUDIO_DIR)]) if os.path.exists(Config.UPLOAD_AUDIO_DIR) else 0,
                "s3": s3.count_files(Config.S3_AUDIO_PREFIX)
            },
            "Transcription": {
                "local": len([f for f in os.listdir(Config.UPLOAD_TRANSCRIPTION_DIR) if f.endswith('.txt')]) if os.path.exists(Config.UPLOAD_TRANSCRIPTION_DIR) else 0,
                "s3": s3.count_files(Config.S3_TRANSCRIPTION_PREFIX)
            },
            "Tribal Audio": {
                "local": len([f for f in os.listdir(Config.TRIBAL_AUDIO_DIR)]) if os.path.exists(Config.TRIBAL_AUDIO_DIR) else 0,
                "s3": s3.count_files(Config.S3_TRIBAL_AUDIO_PREFIX)
            },
            "Tribal Transcription": {
                "local": len([f for f in os.listdir(Config.TRIBAL_TRANSCRIPTION_DIR) if f.endswith('.txt')]) if os.path.exists(Config.TRIBAL_TRANSCRIPTION_DIR) else 0,
                "s3": s3.count_files(Config.S3_TRIBAL_TRANSCRIPTION_PREFIX)
            }
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/sync_s3_prompts", methods=["POST"])
@login_required
def sync_s3_prompts():
    
    try:
        s3 = S3Manager()
        
        # Sync Standard Prompts
        standard_files = s3.list_files(Config.S3_PROMPTS_STANDARD_PREFIX)
        standard_added = 0
        for key in standard_files:
            if key.endswith(".txt"):
                text = s3.read_file(key)
                if text:
                    if add_new_prompt('te', text.strip(), db_type='standard'):
                         standard_added += 1

        # Sync Tribal Prompts
        tribal_files = s3.list_files(Config.S3_PROMPTS_TRIBAL_PREFIX)
        tribal_added = 0
        for key in tribal_files:
            if key.endswith(".txt"):
                text = s3.read_file(key)
                if text:
                    if add_new_prompt('te', text.strip(), db_type='tribal'):
                         tribal_added += 1
                         
        return jsonify({
            "success": True, 
            "message": f"Synced {standard_added} standard prompts and {tribal_added} tribal prompts from S3."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin.admin_login"))
