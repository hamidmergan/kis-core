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
    poppler-utils \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

# Register Calibri → Carlito font substitution for LibreOffice
RUN mkdir -p /usr/lib/libreoffice/share/registry && \
    cat > /usr/lib/libreoffice/share/registry/calibri-substitution.xcu << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" oor:name="Substitutions" oor:package="org.openoffice.VCL">
  <node oor:name="FontSubstitutions">
    <node oor:name="Calibri" oor:op="fuse">
      <prop oor:name="FontSubstitutes"><value>Carlito;Liberation Sans</value></prop>
    </node>
  </node>
</oor:component-data>
EOF

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
