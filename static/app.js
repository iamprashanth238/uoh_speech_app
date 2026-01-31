let recorder;
let chunks = [];
let audioBlob = null;
let recording = false;
let audioContext = null;
let mediaStream = null;
let processor = null;

let currentPromptId = null;

/* DOM ELEMENTS */
const recordBtn = document.getElementById("recordBtn");
const retakeBtn = document.getElementById("retakeBtn");
const saveBtn = document.getElementById("saveBtn");

const promptBox = document.querySelector(".prompt");
const statusBox = document.querySelector(".status");
const progressDots = document.querySelectorAll(".progress span");

const mainSection = document.querySelector("main");
const completionScreen = document.getElementById("completionScreen");
const newSessionBtn = document.getElementById("newSessionBtn");

const userInfoSection = document.getElementById("userInfoSection");
const userInfoForm = document.getElementById("userInfoForm");
const welcomeSection = document.getElementById("welcomeSection");
const startBtn = document.getElementById("startBtn");

/* Mobile-specific optimizations */
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

/* ---------------- WELCOME FLOW ---------------- */
if (startBtn) {
  startBtn.addEventListener("click", () => {
    welcomeSection.style.display = "none";
    userInfoSection.style.display = "block";
    // Trigger reflow to ensure animation plays if needed, though simple display block works too
  });
}

/* ---------------- FORM HANDLING ---------------- */

userInfoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(userInfoForm);
  try {
    const response = await fetch("/submit_user_info", {
      method: "POST",
      body: formData
    });
    const result = await response.json();
    if (result.success) {
      userInfoSection.style.display = "none";
      mainSection.classList.add("fade-in");
      mainSection.style.display = "block";
      loadPrompt();
    } else {
      alert("Error: " + (result.error || "Unknown error"));
    }
  } catch (error) {
    alert("Network error. Please try again.");
  }
});

/* ---------------- UTILITY FUNCTIONS ---------------- */

function updateProgress(completed) {
  // Clear all active dots
  progressDots.forEach(dot => dot.classList.remove("active"));
  // Activate dots up to completed count
  for (let i = 0; i < completed && i < progressDots.length; i++) {
    progressDots[i].classList.add("active");
  }
  // Update status text
  const statusBox = document.querySelector(".status");
  statusBox.textContent = `CONTRIBUTION ${completed + 1} OF 5`;
}

// Convert Float32Array audio data to WAV Blob
function float32ArrayToWav(buffers, sampleRate) {
  const length = buffers.reduce((acc, buffer) => acc + buffer.length, 0);
  const arrayBuffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(arrayBuffer);

  // WAV header
  const writeString = (offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, length * 2, true);

  // Convert float samples to 16-bit PCM
  let offset = 44;
  for (const buffer of buffers) {
    for (let i = 0; i < buffer.length; i++) {
      const sample = Math.max(-1, Math.min(1, buffer[i]));
      view.setInt16(offset, sample * 0x7FFF, true);
      offset += 2;
    }
  }

  return new Blob([arrayBuffer], { type: 'audio/wav' });
}

/* ---------------- PROMPT LOADING (STEP 6) ---------------- */

async function loadPrompt() {
  try {
    const res = await fetch("/api/prompt");
    const data = await res.json();

    if (data.done) {
      if (data.error === "no_prompts") {
        // Show Sorry Message
        mainSection.style.display = "none";
        if (document.getElementById("welcomeSection")) document.getElementById("welcomeSection").style.display = "none";
        if (document.getElementById("userInfoSection")) document.getElementById("userInfoSection").style.display = "none";

        completionScreen.classList.add("fade-in");
        completionScreen.style.display = "block";

        const statusP = completionScreen.querySelector('.status');
        statusP.innerHTML = "SORRY, NO PROMPTS AVAILABLE AT THE MOMENT.<br>PLEASE TRY AGAIN LATER.";

        const controlsDiv = completionScreen.querySelector('.controls');
        controlsDiv.innerHTML = '';

        const title = completionScreen.querySelector('h1');
        if (title) title.innerText = "NOTICE"; // Change "Dhanyavadalu" to Notice or similar? Or keep it. 
        // User asked for "Sorry message", so maybe "Attention" or "Sorry"
        if (title) title.innerText = "SORRY";

        // Add a "Go Back" or "Retry" button
        const homeBtn = document.createElement('button');
        homeBtn.textContent = 'GO TO HOME';
        homeBtn.className = 'submit-btn';
        homeBtn.onclick = () => window.location.reload();
        controlsDiv.appendChild(homeBtn);

        return;
      }

      // Session complete (Success case)
      updateProgress(data.completed || 5);

      // Ensure other sections are hidden
      mainSection.style.display = "none";
      if (document.getElementById("welcomeSection")) document.getElementById("welcomeSection").style.display = "none";
      if (document.getElementById("userInfoSection")) document.getElementById("userInfoSection").style.display = "none";

      completionScreen.classList.add("fade-in");
      completionScreen.style.display = "block";

      // Inject Upload Confirmation Logic here
      const controlsDiv = completionScreen.querySelector('.controls');

      // Clear previous buttons to avoid duplicates/confusion
      controlsDiv.innerHTML = '';

      const confirmBtn = document.createElement('button');
      confirmBtn.id = 'confirmUploadBtn';
      confirmBtn.textContent = 'CONFIRM & UPLOAD TO CLOUD';
      confirmBtn.className = 'submit-btn'; // Reusing style
      confirmBtn.style.marginBottom = '20px';

      const statusP = completionScreen.querySelector('.status');
      statusP.innerHTML = "SESSION COMPLETED.<br>PLEASE CONFIRM TO UPLOAD YOUR RECORDINGS.";

      controlsDiv.appendChild(confirmBtn);

      confirmBtn.onclick = async () => {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "UPLOADING...";

        try {
          const res = await fetch('/finalize_session', { method: 'POST' });
          const result = await res.json();

          if (result.status === 'success') {
            statusP.innerHTML = "UPLOAD SUCCESSFUL!<br>THANK YOU FOR YOUR CONTRIBUTION.";
            confirmBtn.style.display = 'none';

            // Add New Session Button back
            const newSessionBtn = document.createElement('button');
            newSessionBtn.id = 'newSessionBtn';
            newSessionBtn.textContent = 'START NEW SESSION';
            newSessionBtn.onclick = async () => {
              await fetch("/new_session", { method: "POST" });
              window.location.reload();
            };
            controlsDiv.appendChild(newSessionBtn);

          } else {
            statusP.innerHTML = "UPLOAD FAILED. PLEASE TRY AGAIN.";
            confirmBtn.disabled = false;
            confirmBtn.textContent = "RETRY UPLOAD";
          }
        } catch (e) {
          console.error(e);
          statusP.innerHTML = "NETWORK ERROR. PLEASE TRY AGAIN.";
          confirmBtn.disabled = false;
          confirmBtn.textContent = "RETRY UPLOAD";
        }
      };

      return;
    }

    currentPromptId = data.id;
    promptBox.innerText = data.text;

    // Display English Transliteration
    const enPromptBox = document.querySelector('.prompt-english-transliteration');
    if (enPromptBox) {
      if (data.english_text) {
        enPromptBox.innerText = data.english_text;
        enPromptBox.style.display = "block";
      } else {
        enPromptBox.innerText = "";
        enPromptBox.style.display = "none";
      }
    }

    // Reset controls
    recordBtn.style.display = "inline-block";
    recordBtn.textContent = "RECORD";
    retakeBtn.style.display = "none";
    saveBtn.style.display = "none";
    saveBtn.disabled = false;
    saveBtn.textContent = "SAVE";

    // Update progress UI based on server session
    updateProgress(data.completed);
  } catch (error) {
    console.error("Error loading prompt:", error);
    // Show error message to user
    promptBox.innerText = "Error loading prompt. Please refresh the page.";
  }
}

/* ---------------- RECORD FLOW ---------------- */

recordBtn.onclick = async () => {
  if (!recording) {
    try {
      // Check for Web Audio API support
      if (!window.AudioContext && !window.webkitAudioContext) {
        throw new Error("Web Audio API not supported");
      }

      // Request microphone access
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100,
          channelCount: 1
        }
      });

      // Create audio context
      audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 44100
      });

      // Resume context if suspended (required in some browsers)
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      const source = audioContext.createMediaStreamSource(mediaStream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      chunks = [];

      processor.onaudioprocess = (e) => {
        if (recording) {
          const inputBuffer = e.inputBuffer;
          const inputData = inputBuffer.getChannelData(0);
          chunks.push(new Float32Array(inputData));
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      recording = true;
      recordBtn.textContent = "STOP";

    } catch (error) {
      console.error("Error accessing microphone:", error);
      if (error.name === 'NotAllowedError') {
        alert("Microphone access denied. Please allow microphone permissions in your browser settings and try again.");
      } else if (error.name === 'NotFoundError') {
        alert("No microphone found. Please connect a microphone and try again.");
      } else {
        alert("Recording not supported in this browser. Please try a modern browser like Chrome, Firefox, or Edge.");
      }
    }
  } else {
    // Stop recording
    recording = false;
    recordBtn.textContent = "RECORD";

    // Disconnect and cleanup
    if (processor) {
      processor.disconnect();
      processor = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }

    // Convert to WAV
    if (chunks.length > 0) {
      audioBlob = float32ArrayToWav(chunks, 44100);
    }

    recordBtn.style.display = "none";
    retakeBtn.style.display = "inline-block";
    saveBtn.style.display = "inline-block";
  }
};

/* ---------------- RE-TAKE ---------------- */

retakeBtn.onclick = () => {
  audioBlob = null;
  chunks = [];

  // Cleanup audio context and stream
  if (processor) {
    processor.disconnect();
    processor = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close();
    audioContext = null;
  }

  retakeBtn.style.display = "none";
  saveBtn.style.display = "none";
  recordBtn.style.display = "inline-block";
  recordBtn.textContent = "RECORD";
};

/* ---------------- SAVE (STEP 7) ---------------- */

saveBtn.onclick = async () => {
  if (!audioBlob || !currentPromptId) return;

  // Disable button to prevent double submission
  saveBtn.disabled = true;
  saveBtn.textContent = "SAVING...";

  try {
    const fd = new FormData();
    fd.append("audio", audioBlob);
    fd.append("text", promptBox.innerText);
    fd.append("prompt_id", currentPromptId);

    const response = await fetch("/submit", {
      method: "POST",
      body: fd
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();

    // Reset audio state
    audioBlob = null;
    chunks = [];

    // Load next unique prompt
    await loadPrompt();

  } catch (error) {
    console.error("Error saving recording:", error);
    alert("Error saving recording. Please check your connection and try again.");

    // Re-enable button on error
    saveBtn.disabled = false;
    saveBtn.textContent = "SAVE";
  }
};

/* ---------------- NEW SESSION ---------------- */

newSessionBtn.onclick = async () => {
  await fetch("/new_session", { method: "POST" });
  // Full page reload guarantees clean session
  window.location.reload();
};

/* ---------------- INIT ---------------- */

// Commenting out auto-load to force Welcome Screen on refresh
// loadPrompt();
