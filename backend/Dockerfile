FROM python:3.11-slim

WORKDIR /app

# System dependencies (for lxml and Pillow)
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    ffmpeg \
    libreoffice-impress \
    libreoffice-writer \
    default-jre-headless \
    poppler-utils \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

# Register Calibri → Carlito font substitution for LibreOffice
RUN mkdir -p /usr/lib/libreoffice/share/registry && \
    printf '<?xml version="1.0" encoding="UTF-8"?>\n<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" oor:name="Substitutions" oor:package="org.openoffice.VCL">\n<node oor:name="FontSubstitutions">\n<node oor:name="Calibri" oor:op="fuse">\n<prop oor:name="FontSubstitutes"><value>Carlito;Liberation Sans</value></prop>\n</node>\n</node>\n</oor:component-data>' > /usr/lib/libreoffice/share/registry/calibri-substitution.xcu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY entrypoint.sh /usr/local/bin/kis-entrypoint.sh
RUN chmod +x /usr/local/bin/kis-entrypoint.sh

EXPOSE 8000

# Startet ueber das Skript, damit die Prozesszahl aus den vorhandenen Kernen
# kommt statt fest zu sein. Der Schalter dafuer steht oben im Skript und ist
# heute aus, es laeuft also genau ein Prozess wie bisher. Die Celery-Container
# ueberschreiben das per 'command:' in der Compose-Datei.
CMD ["/usr/local/bin/kis-entrypoint.sh"]
