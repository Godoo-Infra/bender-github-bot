#!/bin/bash
docker run --net=host -it -e NGROK_AUTHTOKEN="3JdCmZwYFsmMCdov6YEPL3Uv91W_5sZf4dVfMCR3xVRq2QuPV" ngrok/ngrok:latest http 8080
