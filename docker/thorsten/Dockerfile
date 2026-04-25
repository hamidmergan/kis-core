FROM python:3.10-slim

# System-Dependencies für Coqui TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 espeak-ng && \
    rm -rf /var/lib/apt/lists/*

# Coqui TTS installieren (letzte stabile Version)
RUN pip install --no-cache-dir TTS==0.22.0

# Thorsten-VITS Modell beim Build herunterladen (cached im Layer)
RUN python -c "from TTS.utils.manage import ModelManager; m = ModelManager(); m.download_model('tts_models/de/thorsten/vits')"

EXPOSE 5002

# tts-server mit Thorsten-Modell starten
CMD ["tts-server", "--model_name", "tts_models/de/thorsten/vits", "--port", "5002", "--use_cuda", "true"]
