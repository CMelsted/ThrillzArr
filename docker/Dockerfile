# Runtime binaries for the vendored m4b_merge package
# (previously provided by the ghcr.io/djdembeck/m4b-merge base image,
# whose upstream has since been rewritten in Rust and no longer ships
# the Python package this app vendors in m4b_merge/)
FROM sandreas/ffmpeg:5.0.1-3 AS ffmpeg
FROM sandreas/mp4v2:2.1.1 AS mp4v2
FROM sandreas/fdkaac:2.0.1 AS fdkaac

FROM python:3.12-alpine3.20

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Setup environment variable
ENV APP_HOME=/home/app/web

RUN echo "---- INSTALL RUNTIME PACKAGES ----" && \
    apk add --no-cache --update --upgrade \
    # mp4v2: required libraries
    libstdc++ \
    # m4b-tool: php cli, required extensions and php settings
    php83-cli \
    php83-dom \
    php83-xml \
    php83-mbstring \
    php83-phar \
    php83-tokenizer \
    php83-xmlwriter \
    php83-openssl \
    php83-ctype \
    php83-iconv \
    php83-simplexml \
    && echo "date.timezone = UTC" >> /etc/php83/php.ini \
    && ln -sf /usr/bin/php83 /bin/php

# Add su-exec for easy step-down from root; symlinked as gosu since
# entrypoint.sh uses gosu syntax (argument-compatible)
RUN apk add --no-cache --update --upgrade su-exec \
    && ln -sf /sbin/su-exec /usr/local/bin/gosu

# Add ffmpeg, mp4v2 and fdkaac binaries
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/
COPY --from=ffmpeg /usr/local/bin/ffprobe /usr/local/bin/
COPY --from=mp4v2 /usr/local/bin/mp4* /usr/local/bin/
COPY --from=mp4v2 /usr/local/lib/libmp4v2* /usr/local/lib/
COPY --from=fdkaac /usr/local/bin/fdkaac /usr/local/bin/

# Pinned: upstream's "latest" asset naming has changed before and broken builds
ARG M4B_TOOL_DOWNLOAD_LINK="https://github.com/sandreas/m4b-tool/releases/download/v0.5.2/m4b-tool.phar"

RUN echo "---- INSTALL M4B-TOOL ----" \
    && wget "${M4B_TOOL_DOWNLOAD_LINK}" -O /usr/local/bin/m4b-tool \
    && chmod +x /usr/local/bin/m4b-tool

# Where your code lives
WORKDIR $APP_HOME

# Copy the necessary files to the container
COPY requirements.txt .

# Run this command to install all dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy whole project to your docker home directory.
COPY bragibooks_proj $APP_HOME/bragibooks_proj/
COPY importer $APP_HOME/importer/
COPY m4b_merge $APP_HOME/m4b_merge/
COPY utils $APP_HOME/utils/
COPY manage.py $APP_HOME

# Copy entrypoint file
COPY docker/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Port where the Django app runs
EXPOSE 8000

# Entrypoint for the container
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
