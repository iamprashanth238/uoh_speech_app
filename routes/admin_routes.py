from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, Response
import os, json, csv, io
from datetime import datetime
from config import Config
from database import add_new_prompt, get_prompt_stats, get_total_recordings_count, get_all_recordings
from utils.s3_utils import S3Manager

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Invalid credentials")
    
    return render_template("admin_login.html")


@admin_bp.route("/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin.admin_login"))
    
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
        
        # 5. Metadata / User Records (Now from Database for reliability)
        metadata_count = get_total_recordings_count()
        
        print(f"DEBUG DASHBOARD: Audio={audio_count}, Trans={transcription_count}, StdPrompts={prompt_stats}, Tribal={tribal_prompt_stats}")
        
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
def admin_metadata():
    if not session.get("admin"):
        return redirect(url_for("admin.admin_login"))
    
    # Get recordings from database
    recordings = get_all_recordings()
    metadata_count = len(recordings)
    
    return render_template("admin_metadata.html", 
                         metadata_count=metadata_count,
                         recordings=recordings)

@admin_bp.route("/metadata/download")
def download_metadata():
    if not session.get("admin"):
        return redirect(url_for("admin.admin_login"))
    
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
def add_prompt():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
    language = request.form.get("language", "te")
    text = request.form.get("text", "").strip()
    db_type = request.form.get("db_type", "standard")
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        # Generate a unique ID (S3-only mode)
        import uuid
        prompt_uid = uuid.uuid4().hex[:8]
        
        if db_type == 'tribal':
            prompt_prefix = Config.S3_PROMPTS_TRIBAL_PREFIX
        else:
            prompt_prefix = Config.S3_PROMPTS_STANDARD_PREFIX
            
        s3 = S3Manager()
        
        # Upload individual prompt text file
        # Filename format: UOH_{uuid}.txt
        s3_key = f"{prompt_prefix}UOH_{prompt_uid}.txt"
        
        if s3.upload_string(text, s3_key):
             return jsonify({"success": True, "message": f"Prompt added to S3 ({db_type}) as {s3_key}"})
        else:
             return jsonify({"error": "Failed to upload to S3"}), 500
             
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
def upload_prompts():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401

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
            S3_PROMPT_PREFIX = "prompts/tribal/"
        else:
            S3_PROMPT_PREFIX = "prompts/standard/"

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
            lang_col = field_map.get("language")
            id_col = field_map.get("prompt_id")

            for idx, row in enumerate(reader, start=1):
                text = (row.get(text_col) or "").strip()
                if not text:
                    continue

                language = (row.get(lang_col) if lang_col else None) or default_language
                prompt_id = row.get(id_col) if id_col else f"row_{idx}"

                prompts_to_add.append((language, text))

                filename = safe_filename(f"{prompt_id}_{language}.txt")
                path = os.path.join(temp_dir, filename)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)

                txt_files.append(path)

        # ================= XLSX =================
        else:
            df = pd.read_excel(io.BytesIO(file_content))

            cols = {str(c).lower(): c for c in df.columns}
            if "text" not in cols:
                return jsonify({"error": "Excel file must contain a 'text' column"}), 400

            text_col = cols["text"]
            lang_col = cols.get("language")
            id_col = cols.get("prompt_id")

            for idx, row in df.iterrows():
                text = str(row[text_col]).strip()
                if not text or text.lower() == "nan":
                    continue

                language = (row[lang_col] if lang_col else None) or default_language
                prompt_id = row[id_col] if id_col else f"row_{idx+1}"

                prompts_to_add.append((language, text))

                filename = safe_filename(f"{prompt_id}_{language}.txt")
                path = os.path.join(temp_dir, filename)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)

                txt_files.append(path)

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
        
        for path in txt_files:
            try:
                filename = os.path.basename(path)
                # Ensure it has a unique prefix if not present?
                # For safety, let's prepend UOH_ if not present
                if not filename.startswith("UOH_") and not filename.startswith("row_"):
                     filename = f"UOH_{filename}"
                     
                s3_key = f"{S3_PROMPT_PREFIX}{filename}"
                
                if s3.upload_file(path, s3_key):
                    success_count += 1
            except Exception as e:
                print(f"Failed to upload {path}: {e}")

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
def s3_status():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
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
def sync_s3_prompts():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
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
