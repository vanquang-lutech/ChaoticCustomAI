"""Aggregates every v1 route onto one router."""

from fastapi import APIRouter

from src.api.v1 import custom_text, files, generate_image, jobs, upload, usage

api_router = APIRouter()
api_router.include_router(upload.router)
api_router.include_router(generate_image.router)
api_router.include_router(custom_text.router)
api_router.include_router(jobs.router)
api_router.include_router(files.router)
api_router.include_router(usage.router)
