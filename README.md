# UOH Speech Data Collection Tool

A Flask-based web application for collecting Telugu speech data with user metadata.

## Features

- User information collection (age, gender, location, state)
- Audio recording and transcription
- Admin dashboard with statistics
- Metadata export functionality
- Hugging Face integration for data storage

## Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd uoh-speech-flask-app
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Copy `.env.example` to `.env` and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Required environment variables:
   - `ADMIN_USERNAME`: Admin login username
   - `ADMIN_PASSWORD`: Admin login password
   - `HF_TOKEN`: Your Hugging Face API token (get from https://huggingface.co/settings/tokens)
   - `HF_REPO`: Name of your Hugging Face repository (will be created if it doesn't exist)
   - `HF_USERNAME`: Your Hugging Face username

4. **Run the application**
   ```bash
   python app.py
   ```

## Hugging Face Dataset

When you upload data, the application automatically creates a Hugging Face dataset with:

- **Dataset Card**: Comprehensive README.md with dataset description, statistics, and usage instructions
- **Metadata JSON**: Structured metadata file (`dataset_infos.json`) with dataset information
- **Organized Files**: Audio and transcription files in separate folders
- **Automatic Updates**: Dataset card and metadata are updated with each new upload

### Dataset Structure on HF:

```
your-username/your-repo/
├── README.md                    # Dataset card with description and stats
├── dataset_infos.json          # Structured metadata
├── audio/
│   ├── UOH_abc123.wav
│   └── ...
├── transcription/
│   ├── UOH_abc123.txt
│   ├── UOH_abc123_metadata.json
│   └── ...
```

### Accessing Your Dataset:

```python
from datasets import load_dataset

# Load your dataset
dataset = load_dataset("your-username/your-repo")

# The dataset will have the structure described in the metadata
for example in dataset['train']:
    print(example)
```

## Usage

1. Access the application at `http://localhost:5000`
2. Users fill out their information and record audio
3. Admins can log in at `/admin/login` to view statistics and download metadata
4. All data is stored in the configured Hugging Face repository

## File Structure

- `audio/`: Audio files (.wav)
- `transcription/`: Text transcriptions (.txt) and metadata (.json)

## Admin Features

- View upload statistics
- Download metadata as CSV
- Access Hugging Face repository
- Manage prompts

## License

[Add your license here]
